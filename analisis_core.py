"""Módulo de lógica para buscar y analizar menciones de términos en la web.

Toda la lógica de negocio vive aquí para que la interfaz (Streamlit u otras)
pueda reutilizarla sin dependencias cruzadas.
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

# Número fijo de resultados web que se descargarán y analizarán.
# Nota: es una muestra, no un censo completo de toda la web.
MAX_RESULTADOS_WEB = 200


# =========================
# UTILIDADES DE STOPWORDS
# =========================
def asegurar_stopwords_espanol() -> List[str]:
    """Devuelve las stopwords en español, descargándolas si es necesario."""

    try:
        return stopwords.words("spanish")
    except LookupError:
        nltk.download("stopwords")
        return stopwords.words("spanish")
    except Exception:
        # Si ocurre cualquier error inesperado, se devuelve una lista vacía para
        # no interrumpir el flujo general.
        return []


# =========================
# LIMPIEZA Y NORMALIZACIÓN DE TEXTO
# =========================
def limpiar_texto(texto: str) -> str:
    """Limpia un texto eliminando ruido para facilitar el análisis.

    Pasos aplicados:
    1. Minúsculas.
    2. Elimina URLs, menciones, hashtags y números.
    3. Deja solo letras y espacios (sin signos de puntuación).
    4. Quita acentos con ``unidecode``.
    5. Compacta espacios múltiples.
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
# DESCARGA Y EXTRACCIÓN DE TEXTO DE PÁGINAS
# =========================
def extraer_texto_de_url(url: str, timeout: int = 10) -> str:
    """Descarga una URL y concatena el texto de sus párrafos.

    Si ocurre algún error al descargar o parsear, devuelve una cadena vacía.
    """

    try:
        respuesta = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if respuesta.status_code != 200:
            return ""

        soup = BeautifulSoup(respuesta.text, "html.parser")
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(parrafos)
    except Exception:
        return ""


# =========================
# BÚSQUEDA Y CONTEO DE MENCIONES
# =========================
def _construir_query(grupo_terminos: List[str]) -> str:
    """Construye una query simple uniendo términos con OR."""

    if not grupo_terminos:
        return ""
    termino_principal = '"' + '" OR "'.join(grupo_terminos) + '"'
    return termino_principal


def _contar_menciones_en_texto(
    texto_limpio: str, grupo_terminos: List[str]
) -> Dict[str, int]:
    """Cuenta menciones por término en un texto ya limpiado."""

    palabras_texto = texto_limpio.split()
    conteo: Dict[str, int] = {}
    for termino in grupo_terminos:
        termino_limpio = limpiar_texto(termino)
        palabras_termino = termino_limpio.split()
        if not palabras_termino:
            conteo[termino] = 0
            continue
        menciones = sum(palabras_texto.count(p) for p in palabras_termino)
        conteo[termino] = menciones
    return conteo


def buscar_en_web(
    grupo_terminos: List[str], max_resultados: int = MAX_RESULTADOS_WEB
) -> pd.DataFrame:
    """Busca un grupo de términos y devuelve páginas con menciones.

    Los resultados se basan en los primeros ``max_resultados`` devueltos por el
    motor de búsqueda (muestra, no censo completo de la web).
    """

    if not grupo_terminos:
        return pd.DataFrame()

    query = _construir_query(grupo_terminos)
    registros: List[Dict[str, object]] = []

    with DDGS() as buscador:
        for resultado in buscador.text(query, max_results=max_resultados):
            url = resultado.get("href") or resultado.get("url")
            if not url:
                continue

            titulo = resultado.get("title") or ""
            snippet = resultado.get("body") or resultado.get("snippet") or ""

            texto = extraer_texto_de_url(url)
            if not texto:
                continue

            texto_limpio = limpiar_texto(texto)
            menciones_por_termino = _contar_menciones_en_texto(
                texto_limpio, grupo_terminos
            )
            menciones_totales = sum(menciones_por_termino.values())
            if menciones_totales == 0:
                continue

            registro: Dict[str, object] = {
                "titulo": titulo,
                "url": url,
                "snippet": snippet,
                "texto": texto,
                "menciones_totales_pagina": menciones_totales,
            }

            for idx, termino in enumerate(grupo_terminos, start=1):
                columna = f"menciones_termino_{idx}"
                registro[columna] = menciones_por_termino.get(termino, 0)

            registros.append(registro)

    return pd.DataFrame(registros)


# =========================
# PALABRAS ASOCIADAS
# =========================
def _generar_palabras_limpias(textos: Iterable[str]) -> List[str]:
    """Convierte textos en una lista de palabras limpias."""

    palabras: List[str] = []
    for texto in textos:
        texto_limpio = limpiar_texto(texto)
        if texto_limpio:
            palabras.extend(texto_limpio.split())
    return palabras


def contar_palabras_asociadas(
    df_paginas: pd.DataFrame,
    grupo_terminos: List[str],
    top_n: int = 30,
) -> Tuple[pd.DataFrame, Counter]:
    """Calcula las palabras asociadas más frecuentes.

    Usa solo páginas con menciones. Excluye stopwords, palabras de los términos y
    palabras cortas (<=2 caracteres).
    """

    if df_paginas.empty:
        return pd.DataFrame(columns=["palabra", "frecuencia"]), Counter()

    textos_relevantes = df_paginas.loc[
        df_paginas["menciones_totales_pagina"] > 0, "texto"
    ].tolist()

    todas_las_palabras = _generar_palabras_limpias(textos_relevantes)

    stopwords_es = set(asegurar_stopwords_espanol())
    palabras_terminos = set()
    for termino in grupo_terminos:
        palabras_terminos.update(limpiar_texto(termino).split())

    palabras_filtradas = [
        palabra
        for palabra in todas_las_palabras
        if palabra not in stopwords_es
        and palabra not in palabras_terminos
        and len(palabra) > 2
    ]

    contador = Counter(palabras_filtradas)
    top_palabras = contador.most_common(top_n)
    df_top_palabras = pd.DataFrame(top_palabras, columns=["palabra", "frecuencia"])
    return df_top_palabras, contador


# =========================
# ORQUESTADOR PRINCIPAL
# =========================
def analizar_menciones_web(
    grupo_terminos: List[str],
    fecha_desde: str,
    fecha_hasta: str,
    top_n: int = 30,
    max_resultados: int = MAX_RESULTADOS_WEB,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    """Ejecuta la búsqueda web y devuelve páginas, top palabras y estadísticas."""

    df_paginas = buscar_en_web(grupo_terminos, max_resultados=max_resultados)

    if df_paginas.empty:
        resumen = {
            "terminos": grupo_terminos,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "total_paginas_consultadas": 0,
            "paginas_con_menciones": 0,
            "menciones_totales_grupo": 0,
            "menciones_por_termino": {t: 0 for t in grupo_terminos},
            "promedio_menciones_por_pagina": 0,
        }
        return df_paginas, pd.DataFrame(columns=["palabra", "frecuencia"]), resumen

    df_top_palabras, _ = contar_palabras_asociadas(
        df_paginas, grupo_terminos, top_n=top_n
    )

    menciones_por_termino_total: Dict[str, int] = {}
    for idx, termino in enumerate(grupo_terminos, start=1):
        columna = f"menciones_termino_{idx}"
        if columna in df_paginas.columns:
            menciones_por_termino_total[termino] = int(df_paginas[columna].sum())
        else:
            menciones_por_termino_total[termino] = 0

    paginas_con_menciones = int((df_paginas["menciones_totales_pagina"] > 0).sum())
    menciones_totales_grupo = int(df_paginas["menciones_totales_pagina"].sum())
    promedio = (
        menciones_totales_grupo / paginas_con_menciones
        if paginas_con_menciones > 0
        else 0
    )

    resumen = {
        "terminos": grupo_terminos,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "total_paginas_consultadas": len(df_paginas),
        "paginas_con_menciones": paginas_con_menciones,
        "menciones_totales_grupo": menciones_totales_grupo,
        "menciones_por_termino": menciones_por_termino_total,
        "promedio_menciones_por_pagina": promedio,
    }

    return df_paginas, df_top_palabras, resumen
