"""Módulo central con la lógica de búsqueda y análisis de menciones web.

Incluye utilidades para:
- Búsqueda en la web usando DuckDuckGo (vía ``ddgs``).
- Limpieza de texto y normalización.
- Conteo de menciones de un término.
- Identificación de palabras asociadas más frecuentes.
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

# Número fijo de resultados web a recuperar. Modificar aquí si se necesita.
MAX_RESULTADOS_WEB = 50


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
        # Si falla la descarga, devolvemos lista vacía para no interrumpir el flujo.
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
    termino: str, max_resultados: int = MAX_RESULTADOS_WEB
) -> pd.DataFrame:
    """Busca el término en la web con DuckDuckGo y devuelve un DataFrame.

    Cada fila representa una página donde aparece el término al menos una vez.
    Columnas mínimas: titulo, url, texto, num_menciones_termino.
    """

    resultados: List[Dict[str, str | int]] = []
    termino_patron = re.compile(re.escape(termino), flags=re.IGNORECASE)

    with DDGS() as buscador:
        for resultado in buscador.text(termino, max_results=max_resultados):
            url = resultado.get("href") or resultado.get("url")
            if not url:
                continue

            titulo = resultado.get("title") or ""
            snippet = resultado.get("body") or resultado.get("snippet") or ""

            texto = extraer_texto_de_url(url)
            if not texto:
                continue

            if not termino_patron.search(texto):
                continue

            num_menciones = len(re.findall(termino_patron, texto))
            resultados.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "snippet": snippet,
                    "texto": texto,
                    "num_menciones_termino": num_menciones,
                }
            )

    return pd.DataFrame(resultados)


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


def contar_palabras_asociadas(
    df_paginas: pd.DataFrame, termino: str, top_n: int = 30
) -> Tuple[List[Tuple[str, int]], Counter]:
    """Calcula las palabras asociadas más frecuentes.

    Excluye stopwords, palabras del término y palabras con longitud <= 2.
    Devuelve la lista de las ``top_n`` más frecuentes y el ``Counter`` completo.
    """

    stopwords_es = set(asegurar_stopwords_espanol())
    palabras_termino = set(limpiar_texto(termino).split())

    # Usar solo los textos donde el término fue mencionado al menos una vez.
    textos_relevantes = df_paginas.loc[
        df_paginas["num_menciones_termino"] >= 1, "texto"
    ].tolist()

    todas_las_palabras = _generar_palabras_limpias(textos_relevantes)

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


# =========================
# PIPELINE PRINCIPAL REUTILIZABLE
# =========================
def analizar_menciones_web(
    termino: str,
    fecha_desde: str,
    fecha_hasta: str,
    top_n: int = 30,
    max_resultados_web: int = MAX_RESULTADOS_WEB,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str | int]]:
    """Ejecuta la búsqueda web y devuelve páginas, top palabras y métricas."""

    df_paginas = buscar_en_web(termino=termino, max_resultados=max_resultados_web)

    if df_paginas.empty:
        resumen = {
            "termino": termino,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "total_paginas_con_mencion": 0,
            "total_menciones_termino": 0,
        }
        return df_paginas, pd.DataFrame(columns=["palabra", "frecuencia"]), resumen

    top_palabras, contador = contar_palabras_asociadas(df_paginas, termino, top_n=top_n)
    df_top_palabras = pd.DataFrame(top_palabras, columns=["palabra", "frecuencia"])

    resumen = {
        "termino": termino,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "total_paginas_con_mencion": len(df_paginas),
        "total_menciones_termino": int(df_paginas["num_menciones_termino"].sum()),
    }

    return df_paginas, df_top_palabras, resumen
