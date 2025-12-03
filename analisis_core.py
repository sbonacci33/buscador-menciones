"""Módulo central para buscar y analizar menciones de términos en la web.

Toda la lógica de negocio vive aquí para que la interfaz (Streamlit u otras)
pueda reutilizarla sin dependencias cruzadas.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Counter as CounterType
from typing import Dict, Iterable, List, Tuple

import nltk
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from nltk.corpus import stopwords
from unidecode import unidecode

# Opciones de profundidad amigables para el usuario. Representan cuántos
# resultados se consultan como muestra (no toda la web).
PROFUNDIDAD_OPCIONES: Dict[str, int] = {
    "Rápido": 50,
    "Normal": 100,
    "Profundo": 200,
}

# Modos válidos para contar menciones.
MODOS_COINCIDENCIA_VALIDOS = {"frase_exacta", "todas_las_palabras", "cualquiera"}


# =========================
# UTILIDADES DE STOPWORDS
# =========================
_stopwords_es: set | None = None


def asegurar_stopwords_espanol() -> set[str]:
    """Devuelve las stopwords en español normalizadas sin tildes."""

    import nltk

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
def _normalizar_grupo_terminos(grupo_terminos: List[str]) -> List[str]:
    """Elimina términos vacíos y limita la lista a 3 elementos."""

    return [termino.strip() for termino in grupo_terminos if termino and termino.strip()][
        :3
    ]


def _construir_query(
    grupo_terminos: List[str], modo_coincidencia: str, fecha_desde: str | None, fecha_hasta: str | None
) -> str:
    """Construye una query combinando los términos y el rango de fechas."""

    if not grupo_terminos:
        return ""

    if modo_coincidencia == "cualquiera":
        base_query = " OR ".join([f'"{t}"' for t in grupo_terminos])
    elif modo_coincidencia == "todas_las_palabras":
        base_query = " ".join([f'"{t}"' for t in grupo_terminos])
    else:
        # frase_exacta como caso por defecto
        base_query = " OR ".join([f'"{t}"' for t in grupo_terminos])

    filtros_fecha: List[str] = []
    if fecha_desde:
        filtros_fecha.append(f"after:{fecha_desde}")
    if fecha_hasta:
        filtros_fecha.append(f"before:{fecha_hasta}")

    if filtros_fecha:
        return f"{base_query} {' '.join(filtros_fecha)}"
    return base_query


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
        # Número de veces que aparecen todas las palabras (mínimo común)
        return min(conteos.get(p, 0) for p in palabras_termino)

    # Modo "cualquiera": suma de apariciones individuales
    return sum(conteos.get(p, 0) for p in palabras_termino)


def _contar_menciones_en_texto(
    texto_limpio: str, grupo_terminos: List[str], modo_coincidencia: str
) -> Dict[str, int]:
    """Cuenta menciones por término en un texto ya limpiado."""

    conteo: Dict[str, int] = {}
    for termino in grupo_terminos:
        conteo[termino] = _contar_menciones_termino(
            texto_limpio, termino, modo_coincidencia
        )
    return conteo


def _filtrar_por_dominio(url: str, dominio_filtro: str | None) -> bool:
    """Devuelve True si la URL pasa el filtro de dominio (o no hay filtro)."""

    if not dominio_filtro:
        return True
    return dominio_filtro.lower() in url.lower()


def buscar_en_web(
    grupo_terminos: List[str],
    profundidad: str = "Normal",
    modo_coincidencia: str = "frase_exacta",
    idioma: str = "es",
    dominio_filtro: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> pd.DataFrame:
    """Busca un grupo de términos y devuelve páginas con menciones.

    Los resultados se basan en los primeros N resultados devueltos por el motor
    de búsqueda (muestra, no censo completo de la web).
    """

    grupo_terminos = _normalizar_grupo_terminos(grupo_terminos)
    if not grupo_terminos:
        return pd.DataFrame()

    max_resultados = PROFUNDIDAD_OPCIONES.get(profundidad, PROFUNDIDAD_OPCIONES["Normal"])
    modo = modo_coincidencia if modo_coincidencia in MODOS_COINCIDENCIA_VALIDOS else "frase_exacta"

    query = _construir_query(grupo_terminos, modo, fecha_desde, fecha_hasta)
    registros: List[Dict[str, object]] = []

    try:
        with DDGS() as buscador:
            for resultado in buscador.text(
                query, max_results=max_resultados, safesearch="moderate"
            ):
                url = resultado.get("href") or resultado.get("url")
                if not url or not _filtrar_por_dominio(url, dominio_filtro):
                    continue

                titulo = resultado.get("title") or ""
                snippet = resultado.get("body") or resultado.get("snippet") or ""

                texto = extraer_texto_de_url(url)
                if not texto:
                    continue

                texto_limpio = limpiar_texto(texto)
                menciones_por_termino = _contar_menciones_en_texto(
                    texto_limpio, grupo_terminos, modo
                )
                menciones_totales = sum(menciones_por_termino.values())
                if menciones_totales == 0:
                    # Si no hay menciones, se descarta la página de la muestra
                    continue

                # Si se especificaron múltiples términos, todos deben aparecer
                if len(grupo_terminos) > 1 and any(
                    menciones_por_termino.get(termino, 0) == 0 for termino in grupo_terminos
                ):
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
    except Exception as error:  # pragma: no cover - dependencia externa
        print(
            "Error al buscar en la web con ddgs. "
            "Revisa la instalación de la librería o tu conexión a Internet."
        )
        print(f"Detalle: {error}")
        return pd.DataFrame()

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
) -> Tuple[pd.DataFrame, CounterType[str]]:
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
    df_paginas: pd.DataFrame, grupo_terminos: List[str], top_n: int = 20
) -> pd.DataFrame:
    """Calcula los bigramas más frecuentes excluyendo stopwords y términos."""

    if df_paginas.empty:
        return pd.DataFrame(columns=["bigram", "frecuencia"])

    textos_relevantes = df_paginas.loc[
        df_paginas["menciones_totales_pagina"] > 0, "texto"
    ].tolist()

    palabras = _generar_palabras_limpias(textos_relevantes)
    stopwords_es = asegurar_stopwords_espanol()
    palabras_terminos = set()
    for termino in grupo_terminos:
        palabras_terminos.update(limpiar_texto(termino).split())

    palabras_filtradas = [
        p
        for p in palabras
        if p not in stopwords_es and p not in palabras_terminos and len(p) > 2
    ]

    bigramas = [
        f"{palabras_filtradas[i]} {palabras_filtradas[i + 1]}"
        for i in range(len(palabras_filtradas) - 1)
    ]
    contador: CounterType[str] = Counter(bigramas)
    df_top_bigramas = pd.DataFrame(
        contador.most_common(top_n), columns=["bigram", "frecuencia"]
    )
    return df_top_bigramas


# =========================
# ORQUESTADOR PRINCIPAL
# =========================
def analizar_menciones_web(
    grupo_terminos: List[str],
    fecha_desde: str,
    fecha_hasta: str,
    profundidad: str = "Normal",
    modo_coincidencia: str = "frase_exacta",
    dominio_filtro: str | None = None,
    top_n_palabras: int = 30,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    """Ejecuta la búsqueda web y devuelve páginas, top palabras y estadísticas."""

    df_paginas = buscar_en_web(
        grupo_terminos,
        profundidad=profundidad,
        modo_coincidencia=modo_coincidencia,
        dominio_filtro=dominio_filtro,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    if not df_paginas.empty:
        df_paginas = df_paginas.sort_values(
            by="menciones_totales_pagina", ascending=False
        ).head(20)

    if df_paginas.empty:
        resumen = {
            "terminos": grupo_terminos,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "profundidad": profundidad,
            "modo_coincidencia": modo_coincidencia,
            "dominio_filtro": dominio_filtro,
            "total_paginas_consultadas": 0,
            "paginas_con_menciones": 0,
            "menciones_totales_grupo": 0,
            "menciones_por_termino": {t: 0 for t in grupo_terminos},
            "promedio_menciones_por_pagina": 0,
            "paginas_top_mostradas": 0,
        }
        return df_paginas, pd.DataFrame(columns=["palabra", "frecuencia"]), resumen

    df_top_palabras, _ = contar_palabras_asociadas(
        df_paginas, grupo_terminos, top_n=top_n_palabras
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
        "profundidad": profundidad,
        "modo_coincidencia": modo_coincidencia,
        "dominio_filtro": dominio_filtro,
        "max_resultados_muestra": PROFUNDIDAD_OPCIONES.get(
            profundidad, PROFUNDIDAD_OPCIONES["Normal"]
        ),
        "total_paginas_consultadas": len(df_paginas),
        "paginas_con_menciones": paginas_con_menciones,
        "menciones_totales_grupo": menciones_totales_grupo,
        "menciones_por_termino": menciones_por_termino_total,
        "promedio_menciones_por_pagina": promedio,
        "paginas_top_mostradas": len(df_paginas),
    }

    return df_paginas, df_top_palabras, resumen
