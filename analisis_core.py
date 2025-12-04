"""Lógica principal de negocio para el análisis de menciones en la web."""
from __future__ import annotations

import re
from collections import Counter
from typing import Counter as CounterType
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import nltk
import pandas as pd
from nltk.corpus import stopwords
from unidecode import unidecode

from datos_repository import (
    guardar_pagina,
    inicializar_bd,
    registrar_menciones,
)
from fuentes_web import PROFUNDIDAD_OPCIONES, ResultadoBusqueda, buscar_paginas_web

# Modos válidos para contar menciones.
MODOS_COINCIDENCIA_VALIDOS = {"frase_exacta", "todas_las_palabras", "cualquiera"}

# Caché de stopwords
_stopwords_es: set | None = None


# =========================
# UTILIDADES DE STOPWORDS
# =========================
def asegurar_stopwords_espanol() -> set[str]:
    """Devuelve las stopwords en español normalizadas sin tildes."""

    global _stopwords_es
    if _stopwords_es is not None:
        return _stopwords_es

    try:
        palabras = stopwords.words("spanish")
    except LookupError:
        nltk.download("stopwords")
        palabras = stopwords.words("spanish")
    except Exception:
        _stopwords_es = set()
        return _stopwords_es

    _stopwords_es = {unidecode(p.lower()) for p in palabras}
    return _stopwords_es


# =========================
# LIMPIEZA Y NORMALIZACIÓN DE TEXTO
# =========================
def limpiar_texto(texto: str) -> str:
    """Limpia un texto eliminando ruido para facilitar el análisis."""

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
# BÚSQUEDA Y CONTEO DE MENCIONES
# =========================
def _normalizar_grupo_terminos(grupo_terminos: List[str]) -> List[str]:
    """Elimina términos vacíos y limita la lista a 5 elementos."""

    return [termino.strip() for termino in grupo_terminos if termino and termino.strip()][:5]


def _contar_menciones_termino(texto_limpio: str, termino: str, modo: str) -> int:
    """Cuenta menciones de un término según el modo de coincidencia elegido."""

    termino_limpio = limpiar_texto(termino)
    if not termino_limpio:
        return 0

    palabras_termino = termino_limpio.split()
    if not palabras_termino:
        return 0

    palabras_texto = texto_limpio.split()

    if modo == "frase_exacta":
        patron = r"\b" + re.escape(termino_limpio) + r"\b"
        return len(re.findall(patron, texto_limpio))

    conteos = Counter(palabras_texto)

    if modo == "todas_las_palabras":
        return min(conteos.get(p, 0) for p in palabras_termino)

    return sum(conteos.get(p, 0) for p in palabras_termino)


def _contar_menciones_en_texto(
    texto_limpio: str, grupo_terminos: List[str], modo_coincidencia: str
) -> Dict[str, int]:
    """Cuenta menciones por término en un texto ya limpiado."""

    conteo: Dict[str, int] = {}
    for termino in grupo_terminos:
        conteo[termino] = _contar_menciones_termino(texto_limpio, termino, modo_coincidencia)
    return conteo


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
    paginas_df: pd.DataFrame, grupo_terminos: List[str], top_n: int = 30
) -> Tuple[pd.DataFrame, CounterType[str]]:
    """Calcula las palabras asociadas más frecuentes."""

    if paginas_df.empty:
        return pd.DataFrame(columns=["palabra", "frecuencia"]), Counter()

    textos_relevantes = paginas_df.loc[
        paginas_df["menciones_totales_pagina"] > 0, "texto"
    ].tolist()

    todas_las_palabras = _generar_palabras_limpias(textos_relevantes)

    stopwords_es = asegurar_stopwords_espanol()
    palabras_terminos = set()
    for termino in grupo_terminos:
        for palabra in limpiar_texto(termino).split():
            palabra_normalizada = unidecode(palabra.lower())
            if palabra_normalizada:
                palabras_terminos.add(palabra_normalizada)

    palabras_filtradas: List[str] = []
    for palabra in todas_las_palabras:
        palabra_normalizada = unidecode(palabra.lower())
        if len(palabra_normalizada) <= 2:
            continue
        if palabra_normalizada in stopwords_es:
            continue
        if palabra_normalizada in palabras_terminos:
            continue
        palabras_filtradas.append(palabra_normalizada)

    contador: CounterType[str] = Counter(palabras_filtradas)
    top_palabras = contador.most_common(top_n)
    df_top_palabras = pd.DataFrame(top_palabras, columns=["palabra", "frecuencia"])
    return df_top_palabras, contador


def contar_bigramas(
    paginas_df: pd.DataFrame, grupo_terminos: List[str], top_n: int = 20
) -> pd.DataFrame:
    """Calcula los bigramas más frecuentes excluyendo stopwords y términos."""

    if paginas_df.empty:
        return pd.DataFrame(columns=["bigram", "frecuencia"])

    textos_relevantes = paginas_df.loc[
        paginas_df["menciones_totales_pagina"] > 0, "texto"
    ].tolist()

    palabras = _generar_palabras_limpias(textos_relevantes)
    stopwords_es = asegurar_stopwords_espanol()
    palabras_terminos = set()
    for termino in grupo_terminos:
        palabras_terminos.update(limpiar_texto(termino).split())

    palabras_filtradas = [
        p for p in palabras if p not in stopwords_es and p not in palabras_terminos and len(p) > 2
    ]

    bigramas = [
        f"{palabras_filtradas[i]} {palabras_filtradas[i + 1]}" for i in range(len(palabras_filtradas) - 1)
    ]
    contador: CounterType[str] = Counter(bigramas)
    df_top_bigramas = pd.DataFrame(contador.most_common(top_n), columns=["bigram", "frecuencia"])
    return df_top_bigramas


# =========================
# ORQUESTADOR PRINCIPAL
# =========================
def _procesar_resultado(
    resultado: ResultadoBusqueda,
    grupo_terminos: List[str],
    modo_coincidencia: str,
) -> Dict[str, object] | None:
    """Convierte un resultado bruto en registro listo para DataFrame y BD."""

    texto_limpio = limpiar_texto(resultado.texto or "")
    menciones_por_termino = _contar_menciones_en_texto(texto_limpio, grupo_terminos, modo_coincidencia)
    menciones_totales = sum(menciones_por_termino.values())
    if menciones_totales == 0:
        return None

    registro: Dict[str, object] = {
        "titulo": resultado.titulo,
        "url": resultado.url,
        "dominio": resultado.dominio or urlparse(resultado.url).netloc,
        "texto": resultado.texto,
        "fecha_publicacion": resultado.fecha_publicacion,
        "menciones_totales_pagina": menciones_totales,
        "menciones_por_termino": menciones_por_termino,
    }

    for idx, termino in enumerate(grupo_terminos, start=1):
        registro[f"menciones_termino_{idx}"] = menciones_por_termino.get(termino, 0)

    return registro


def analizar_menciones_web(
    grupo_terminos: List[str],
    fecha_desde: str,
    fecha_hasta: str,
    profundidad: str = "Normal",
    modo_coincidencia: str = "frase_exacta",
    dominio_filtro: str | None = None,
    top_n_palabras: int = 30,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Ejecuta la búsqueda web y devuelve páginas, top palabras y estadísticas."""

    inicializar_bd()
    grupo_terminos = _normalizar_grupo_terminos(grupo_terminos)
    if not grupo_terminos:
        return pd.DataFrame(), pd.DataFrame(), {}

    modo = modo_coincidencia if modo_coincidencia in MODOS_COINCIDENCIA_VALIDOS else "frase_exacta"

    resultados_web = buscar_paginas_web(
        grupo_terminos=grupo_terminos,
        profundidad=profundidad,
        modo_coincidencia=modo,
        dominio_filtro=dominio_filtro,
    )

    registros: List[Dict[str, object]] = []
    for resultado in resultados_web:
        registro = _procesar_resultado(resultado, grupo_terminos, modo)
        if not registro:
            continue

        pagina_id = guardar_pagina(registro["url"], registro["titulo"], registro["texto"])
        registrar_menciones(pagina_id, registro["menciones_por_termino"])
        registros.append(registro)

    df_paginas = pd.DataFrame(registros)
    if df_paginas.empty:
        resumen = {
            "terminos": grupo_terminos,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "profundidad": profundidad,
            "modo_coincidencia": modo,
            "dominio_filtro": dominio_filtro,
            "total_paginas_consultadas": len(resultados_web),
            "paginas_con_menciones": 0,
            "menciones_totales_grupo": 0,
            "menciones_por_termino": {t: 0 for t in grupo_terminos},
            "promedio_menciones_por_pagina": 0,
            "paginas_top_mostradas": 0,
            "dominios_top": {},
        }
        return df_paginas, pd.DataFrame(columns=["palabra", "frecuencia"]), resumen

    df_paginas = df_paginas.sort_values(by="menciones_totales_pagina", ascending=False)

    df_top_palabras, _ = contar_palabras_asociadas(df_paginas, grupo_terminos, top_n=top_n_palabras)

    menciones_por_termino_total: Dict[str, int] = {}
    for idx, termino in enumerate(grupo_terminos, start=1):
        columna = f"menciones_termino_{idx}"
        if columna in df_paginas.columns:
            menciones_por_termino_total[termino] = int(df_paginas[columna].sum())
        else:
            menciones_por_termino_total[termino] = 0

    paginas_con_menciones = int((df_paginas["menciones_totales_pagina"] > 0).sum())
    menciones_totales_grupo = int(df_paginas["menciones_totales_pagina"].sum())
    promedio = menciones_totales_grupo / paginas_con_menciones if paginas_con_menciones > 0 else 0

    dominios_top = (
        df_paginas.groupby("dominio")["url"].count().sort_values(ascending=False).head(10).to_dict()
    )

    resumen = {
        "terminos": grupo_terminos,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "profundidad": profundidad,
        "modo_coincidencia": modo,
        "dominio_filtro": dominio_filtro,
        "max_resultados_muestra": PROFUNDIDAD_OPCIONES.get(profundidad, PROFUNDIDAD_OPCIONES["Normal"]),
        "total_paginas_consultadas": len(resultados_web),
        "paginas_con_menciones": paginas_con_menciones,
        "menciones_totales_grupo": menciones_totales_grupo,
        "menciones_por_termino": menciones_por_termino_total,
        "promedio_menciones_por_pagina": promedio,
        "paginas_top_mostradas": len(df_paginas),
        "dominios_top": dominios_top,
    }

    return df_paginas, df_top_palabras, resumen
