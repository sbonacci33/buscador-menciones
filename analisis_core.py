"""Funciones reutilizables para análisis de menciones en la web.

Este módulo contiene utilidades de búsqueda, limpieza de texto y cálculo de
frecuencias que pueden ser usadas tanto desde consola como desde una interfaz
web en Streamlit.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

import nltk
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from nltk.corpus import stopwords
from unidecode import unidecode


# =========================
# UTILIDADES NLTK
# =========================
def asegurar_stopwords_espanol() -> List[str]:
    """Devuelve las stopwords en español, descargándolas si es necesario."""

    try:
        return stopwords.words("spanish")
    except LookupError:
        nltk.download("stopwords")
        return stopwords.words("spanish")
    except Exception:
        return []


# =========================
# LIMPIEZA DE TEXTO
# =========================
def limpiar_texto(texto: str) -> str:
    """Limpia y normaliza un texto para análisis de frecuencias.

    Pasos principales:
    1. Convierte a minúsculas.
    2. Elimina URLs, menciones, hashtags y números.
    3. Deja solo letras y espacios (quita puntuación y símbolos).
    4. Quita acentos con ``unidecode``.
    5. Reduce espacios múltiples.
    """

    if not isinstance(texto, str):
        return ""

    texto_limpio = texto.lower()
    texto_limpio = re.sub(r"http\S+|www\.\S+", " ", texto_limpio)
    texto_limpio = re.sub(r"[@#]\w+", " ", texto_limpio)
    texto_limpio = re.sub(r"\d+", " ", texto_limpio)
    texto_limpio = re.sub(r"[^a-záéíóúñü\s]", " ", texto_limpio)
    texto_limpio = unidecode(texto_limpio)
    texto_limpio = re.sub(r"\s+", " ", texto_limpio).strip()
    return texto_limpio


# =========================
# BÚSQUEDA EN LA WEB
# =========================
def extraer_texto_de_url(url: str, timeout: int = 10) -> str:
    """Descarga una URL y concatena el texto de sus párrafos.

    Si ocurre algún error al descargar o parsear, devuelve una cadena vacía.
    """

    try:
        respuesta = requests.get(
            url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
        )
        if respuesta.status_code != 200:
            return ""
        soup = BeautifulSoup(respuesta.text, "html.parser")
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(parrafos)
    except Exception:
        return ""


def buscar_en_web(
    termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_web: int
) -> Tuple[pd.DataFrame, int]:
    """Busca el término en la web con DuckDuckGo y devuelve un DataFrame.

    ddgs no permite filtrar por rango de fechas de manera directa, así que el
    filtro es aproximado y depende del motor de búsqueda.
    """

    resultados: List[Dict[str, str | int]] = []
    termino_patron = re.compile(re.escape(termino), flags=re.IGNORECASE)
    total_paginas_consultadas = 0

    with DDGS() as buscador:
        for resultado in buscador.text(keywords=termino, max_results=max_resultados_web):
            url = resultado.get("href") or resultado.get("url")
            if not url:
                continue
            titulo = resultado.get("title") or ""
            fecha = resultado.get("date") or ""
            snippet = resultado.get("body") or resultado.get("snippet") or ""

            texto = extraer_texto_de_url(url)
            if not texto:
                continue

            total_paginas_consultadas += 1

            if not termino_patron.search(texto):
                continue

            num_menciones = len(re.findall(termino_patron, texto))
            resultados.append(
                {
                    "fuente": "web",
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "snippet": snippet,
                    "texto": texto,
                    "num_menciones_termino": num_menciones,
                }
            )

    return pd.DataFrame(resultados), total_paginas_consultadas


# =========================
# ANÁLISIS DE PALABRAS
# =========================
def _generar_palabras_limpias(textos: Iterable[str]) -> List[str]:
    """Devuelve una lista de palabras limpias a partir de un iterable de textos."""

    palabras: List[str] = []
    for texto in textos:
        texto_limpio = limpiar_texto(texto)
        if not texto_limpio:
            continue
        palabras.extend(texto_limpio.split())
    return palabras


def contar_palabras_frecuentes(
    df: pd.DataFrame, termino: str, top_n: int = 30
) -> Tuple[List[Tuple[str, int]], Counter]:
    """Calcula las palabras más frecuentes excluyendo stopwords y el término buscado."""

    stopwords_es = set(asegurar_stopwords_espanol())
    palabras_termino = set(limpiar_texto(termino).split())

    todas_las_palabras = _generar_palabras_limpias(df.get("texto", []))

    palabras_filtradas = [
        palabra
        for palabra in todas_las_palabras
        if palabra not in stopwords_es
        and palabra not in palabras_termino
        and len(palabra) > 2
    ]

    contador = Counter(palabras_filtradas)
    top_palabras = contador.most_common(top_n)
    return top_palabras, contador


def construir_dataframe_frecuencias(
    contador: Counter, top_n: int = 30
) -> pd.DataFrame:
    """Construye un DataFrame ordenado con las ``top_n`` palabras más frecuentes."""

    top_palabras = contador.most_common(top_n)
    return pd.DataFrame(top_palabras, columns=["palabra", "frecuencia"])


# =========================
# PIPELINE PRINCIPAL REUTILIZABLE
# =========================
def analizar_menciones_web(
    termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_web: int, top_n: int = 30
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    """Ejecuta la búsqueda web y devuelve resultados, frecuencias y métricas."""

    df_paginas, total_paginas_consultadas = buscar_en_web(
        termino=termino,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        max_resultados_web=max_resultados_web,
    )

    if df_paginas.empty:
        resumen = {
            "total_paginas_consultadas": total_paginas_consultadas,
            "total_paginas_con_menciones": 0,
            "total_menciones_termino": 0,
        }
        return df_paginas, pd.DataFrame(columns=["palabra", "frecuencia"]), resumen

    top_palabras, contador = contar_palabras_frecuentes(df_paginas, termino, top_n=top_n)
    df_frecuencias = pd.DataFrame(top_palabras, columns=["palabra", "frecuencia"])

    resumen = {
        "total_paginas_consultadas": total_paginas_consultadas,
        "total_paginas_con_menciones": len(df_paginas),
        "total_menciones_termino": int(df_paginas["num_menciones_termino"].sum()),
    }

    return df_paginas, df_frecuencias, resumen
