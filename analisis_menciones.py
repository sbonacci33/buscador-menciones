#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrucciones de instalación (ejecutar en la terminal, idealmente dentro de un entorno virtual):

    pip install -r requirements.txt

Dependencias principales:
    - ddgs (búsqueda web DuckDuckGo)
    - requests
    - beautifulsoup4
    - pandas
    - nltk
    - unidecode

"""

import re
from collections import Counter
from datetime import datetime
from typing import List, Tuple

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
        print("Descargando stopwords de NLTK en español...")
        nltk.download("stopwords")
        return stopwords.words("spanish")
    except Exception as exc:
        print(f"No se pudieron cargar las stopwords: {exc}")
        return []


# =========================
# LIMPIEZA DE TEXTO
# =========================
def limpiar_texto(texto: str) -> str:
    """Limpia y normaliza un texto para análisis de frecuencias."""

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
    """Descarga una URL y concatena los párrafos principales."""

    try:
        respuesta = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if respuesta.status_code != 200:
            return ""
        soup = BeautifulSoup(respuesta.text, "html.parser")
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(parrafos)
    except Exception as exc:
        print(f"No se pudo procesar {url}: {exc}")
        return ""


def buscar_en_web(termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_web: int) -> pd.DataFrame:
    """Busca el término en la web con DuckDuckGo y devuelve un DataFrame con las páginas válidas."""

    resultados = []
    termino_patron = re.compile(re.escape(termino), flags=re.IGNORECASE)

    with DDGS() as buscador:
        # ddgs no filtra fechas de forma nativa; el rango es aproximado
        for resultado in buscador.text(keywords=termino, max_results=max_resultados_web):
            url = resultado.get("href") or resultado.get("url")
            if not url:
                continue
            titulo = resultado.get("title") or ""
            fecha = resultado.get("date") or ""

            texto = extraer_texto_de_url(url)
            if not texto:
                continue

            if not termino_patron.search(texto):
                continue

            num_menciones = len(re.findall(termino_patron, texto))
            resultados.append(
                {
                    "fuente": "web",
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "texto": texto,
                    "num_menciones_termino": num_menciones,
                }
            )

    return pd.DataFrame(resultados)


# =========================
# ANÁLISIS DE PALABRAS
# =========================
def contar_palabras_frecuentes(df: pd.DataFrame, termino: str, top_n: int = 30) -> Tuple[List[Tuple[str, int]], Counter]:
    """Calcula las palabras más frecuentes excluyendo stopwords, el término buscado y palabras cortas."""

    stopwords_es = set(asegurar_stopwords_espanol())
    palabras_termino = set(limpiar_texto(termino).split())

    todas_las_palabras: List[str] = []
    for texto in df.get("texto", []):
        texto_limpio = limpiar_texto(texto)
        if not texto_limpio:
            continue
        for palabra in texto_limpio.split():
            if palabra in stopwords_es:
                continue
            if palabra in palabras_termino:
                continue
            if len(palabra) <= 2:
                continue
            todas_las_palabras.append(palabra)

    contador = Counter(todas_las_palabras)
    top_palabras = contador.most_common(top_n)
    return top_palabras, contador


# =========================
# REDES SOCIALES (PLACEHOLDER)
# =========================
def buscar_en_redes(termino: str, fecha_desde: str, fecha_hasta: str, max_resultados: int) -> pd.DataFrame:  # pragma: no cover
    """Placeholder para búsquedas en redes sociales (no implementado)."""

    print("Módulo de redes sociales no implementado. Se continúa solo con resultados web.")
    return pd.DataFrame(columns=["fuente", "titulo", "url", "fecha", "texto", "num_menciones_termino"])


# =========================
# FUNCIÓN PRINCIPAL
# =========================
def main() -> None:
    """Flujo principal con entrada por consola y guardado de archivos."""

    print("=== Análisis de menciones en la web ===")

    termino = input("Ingrese el término o nombre a analizar (ej: Lionel Messi): ").strip()
    fecha_desde = input("Ingrese la fecha de inicio (YYYY-MM-DD): ").strip()
    fecha_hasta = input("Ingrese la fecha de fin (YYYY-MM-DD): ").strip()
    max_web_str = input("Ingrese la cantidad máxima de resultados web (ej: 50): ").strip()

    try:
        fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
        fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
        if fecha_desde_dt > fecha_hasta_dt:
            print("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
            return
    except ValueError:
        print("Las fechas deben estar en formato YYYY-MM-DD y ser válidas.")
        return

    try:
        max_resultados_web = max(1, int(max_web_str))
    except ValueError:
        print("La cantidad máxima de resultados web debe ser un número entero.")
        return

    print("\nBuscando en la web...")
    df_web = buscar_en_web(termino, fecha_desde, fecha_hasta, max_resultados_web)

    if df_web.empty:
        print("No se obtuvieron resultados web para el término y rango de fechas especificados.")
        return

    df_web.to_csv("paginas_web.csv", index=False, encoding="utf-8")
    print(f"Se guardaron {len(df_web)} páginas en 'paginas_web.csv'.")

    print("\nProcesando textos y calculando frecuencias...")
    top_palabras, contador_completo = contar_palabras_frecuentes(df_web, termino, top_n=30)

    total_paginas_con_mencion = len(df_web)
    total_menciones_termino = int(df_web["num_menciones_termino"].sum())

    print("\n=== Resumen ===")
    print(f"Total de páginas analizadas: {len(df_web)}")
    print(f"Total de páginas que mencionan el término: {total_paginas_con_mencion}")
    print(f"Total de menciones del término: {total_menciones_termino}")

    print("\n=== Top de palabras más frecuentes ===")
    for palabra, frecuencia in top_palabras:
        print(f"{palabra}: {frecuencia}")

    df_freq = pd.DataFrame(list(contador_completo.items()), columns=["palabra", "frecuencia"])
    df_freq = df_freq.sort_values(by="frecuencia", ascending=False)
    df_freq.to_csv("frecuencias_palabras.csv", index=False, encoding="utf-8")
    print("Frecuencias guardadas en 'frecuencias_palabras.csv'.")

    print("\nAnálisis completado.")


if __name__ == "__main__":
    main()
