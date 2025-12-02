#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrucciones de instalación (ejecutar en la terminal, idealmente dentro de un entorno virtual):

    pip install -r requirements.txt

Dependencias principales:
    - duckduckgo-search (para buscar en la web)
    - beautifulsoup4 (para extraer texto de páginas)
    - requests
    - pandas
    - nltk
    - unidecode
    - twscrape (para X/Twitter, si se activa el módulo de redes sociales)

Nota: para usar X/Twitter vía twscrape, el usuario debe configurar sus cuentas previamente
(ver README.md).
"""

import asyncio
import re
from collections import Counter
from datetime import datetime
from typing import List, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from nltk.corpus import stopwords
from unidecode import unidecode

# twscrape solo se usa si el usuario decide incluir redes sociales. Se importa aquí para
# que esté disponible en tiempo de ejecución sin requerir la biblioteca si no se usa.
try:
    from twscrape import API
except ImportError:  # pragma: no cover - depende de instalación opcional
    API = None

import nltk


# =========================
# UTILIDADES NLTK
# =========================
def asegurar_stopwords_espanol() -> List[str]:
    """
    Descarga las stopwords en español de NLTK si aún no están instaladas y devuelve la lista.
    """

    try:
        return stopwords.words("spanish")
    except LookupError:
        print("Descargando stopwords de NLTK en español...")
        nltk.download("stopwords")
        return stopwords.words("spanish")
    except Exception as exc:  # pragma: no cover - fallo inesperado
        print(f"Error al verificar/descargar stopwords de NLTK: {exc}")
        return []


# =========================
# LIMPIEZA DE TEXTO
# =========================
def limpiar_texto(texto: str) -> str:
    """
    Limpia un texto aplicando reglas de normalización para el análisis.

    Pasos:
    1. Minúsculas.
    2. Eliminar URLs.
    3. Eliminar menciones (@usuario) y hashtags (#tema).
    4. Eliminar números.
    5. Eliminar signos de puntuación y caracteres especiales, dejando letras y espacios.
    6. Quitar acentos/tildes con unidecode.
    7. Quitar espacios múltiples.
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
    """Descarga y extrae el texto principal de una página usando BeautifulSoup."""

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(paragraphs)
    except Exception as exc:  # pragma: no cover - errores de red variables
        print(f"No se pudo extraer texto de {url}: {exc}")
        return ""


def buscar_en_web(
    termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_web: int
) -> pd.DataFrame:
    """
    Busca menciones del término en la web usando DuckDuckGo y devuelve un DataFrame.
    """

    resultados = []
    try:
        with DDGS() as ddgs:
            # Se usa la búsqueda de texto general para obtener títulos y snippets.
            for resultado in ddgs.text(
                keywords=termino,
                region="es-es",
                safesearch="moderate",
                max_results=max_resultados_web,
            ):
                url = resultado.get("href")
                titulo = resultado.get("title")
                snippet = resultado.get("body")
                fecha = resultado.get("date")

                texto_url = extraer_texto_de_url(url) if url else ""
                texto_final = texto_url if texto_url else snippet or ""

                resultados.append(
                    {
                        "fuente": "web",
                        "titulo": titulo,
                        "texto": texto_final,
                        "url": url,
                        "fecha": fecha,
                    }
                )
    except Exception as exc:
        print(f"No se pudieron obtener resultados web: {exc}")

    return pd.DataFrame(resultados)


# =========================
# BÚSQUEDA EN REDES SOCIALES (X/TWITTER)
# =========================
async def _buscar_en_redes_async(
    termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_redes: int
) -> pd.DataFrame:
    """Función asíncrona que usa twscrape para buscar tweets."""

    if API is None:
        raise ImportError(
            "twscrape no está instalado. Instala las dependencias opcionales para usar redes sociales."
        )

    api = API()
    # Se asume que el usuario ya configuró cuentas válidas en la base de datos de twscrape.
    await api.pool.login_all()

    query = f'"{termino}" lang:es since:{fecha_desde} until:{fecha_hasta}'
    tweets = []

    async for tweet in api.search(query):
        tweets.append(
            {
                "fuente": "x",
                "fecha": tweet.date,
                "usuario": tweet.user.username,
                "texto": tweet.rawContent,
                "url": f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",
            }
        )
        if len(tweets) >= max_resultados_redes:
            break

    return pd.DataFrame(tweets)


def buscar_en_redes(
    termino: str, fecha_desde: str, fecha_hasta: str, max_resultados_redes: int
) -> pd.DataFrame:
    """Wrapper síncrono para ejecutar la búsqueda de redes sociales."""

    try:
        return asyncio.run(
            _buscar_en_redes_async(termino, fecha_desde, fecha_hasta, max_resultados_redes)
        )
    except Exception as exc:
        print(f"No se pudieron obtener resultados de redes sociales: {exc}")
        return pd.DataFrame()


# =========================
# CÁLCULO DE PALABRAS FRECUENTES
# =========================
def contar_palabras_frecuentes(
    df: pd.DataFrame, termino: str, top_n: int = 30
) -> Tuple[List[Tuple[str, int]], Counter]:
    """
    Calcula palabras más frecuentes excluyendo stopwords, el término buscado y palabras cortas.
    """

    stopwords_es = set(asegurar_stopwords_espanol())
    palabras_termino = set(limpiar_texto(termino).split())

    todas_las_palabras: List[str] = []
    for texto in df.get("texto", []):
        texto_limpio = limpiar_texto(texto)
        if not texto_limpio:
            continue
        palabras = texto_limpio.split()
        for palabra in palabras:
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
# FUNCIÓN PRINCIPAL
# =========================
def main():
    """
    Flujo principal del programa con interacción por consola.
    """

    print("=== Análisis de menciones en la web y redes sociales ===")

    termino = input("Ingrese el término o nombre a analizar (ej: Lionel Messi): ").strip()
    fecha_desde = input("Ingrese la fecha de inicio (YYYY-MM-DD): ").strip()
    fecha_hasta = input("Ingrese la fecha de fin (YYYY-MM-DD): ").strip()
    max_web_str = input("Ingrese la cantidad máxima de resultados web (ej: 50): ").strip()

    incluir_redes = input("¿Desea incluir redes sociales? (s/n): ").strip().lower() == "s"
    max_redes_str = "0"
    if incluir_redes:
        max_redes_str = input(
            "Ingrese la cantidad máxima de resultados de redes sociales (ej: 100): "
        ).strip()

    # Validaciones básicas
    try:
        fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
        fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
        if fecha_desde_dt >= fecha_hasta_dt:
            print("La fecha de inicio debe ser anterior a la fecha de fin.")
            return
    except ValueError:
        print("Las fechas deben estar en formato YYYY-MM-DD y ser válidas.")
        return

    try:
        max_resultados_web = max(1, int(max_web_str))
    except ValueError:
        print("La cantidad máxima de resultados web debe ser un número entero.")
        return

    max_resultados_redes = 0
    if incluir_redes:
        try:
            max_resultados_redes = max(1, int(max_redes_str))
        except ValueError:
            print("La cantidad máxima de resultados de redes debe ser un número entero.")
            return

    # Búsqueda en la web
    print("\nBuscando en la web...")
    df_web = buscar_en_web(termino, fecha_desde, fecha_hasta, max_resultados_web)

    # Búsqueda en redes sociales
    df_redes = pd.DataFrame()
    if incluir_redes:
        print("\nBuscando en X/Twitter...")
        df_redes = buscar_en_redes(termino, fecha_desde, fecha_hasta, max_resultados_redes)

    # Unir resultados
    df_combinado = pd.concat([df_web, df_redes], ignore_index=True)

    if df_combinado.empty:
        print("No se obtuvieron textos suficientes para el análisis.")
        return

    # Guardar fuentes crudas
    try:
        df_combinado.to_csv("resultados_fuentes_crudos.csv", index=False, encoding="utf-8")
        print(f"Se guardaron {len(df_combinado)} resultados en 'resultados_fuentes_crudos.csv'.")
    except Exception as exc:
        print(f"No se pudieron guardar los resultados crudos: {exc}")

    # Calcular frecuencias
    print("\nProcesando textos y calculando frecuencias...")
    top_palabras, contador_completo = contar_palabras_frecuentes(df_combinado, termino, top_n=30)

    if not top_palabras:
        print("No se encontraron palabras significativas después del procesamiento.")
        return

    print("\n=== Top de palabras más frecuentes ===")
    for palabra, frecuencia in top_palabras:
        print(f"{palabra}: {frecuencia}")

    # Guardar frecuencias en CSV
    try:
        df_freq = pd.DataFrame(list(contador_completo.items()), columns=["palabra", "frecuencia"])
        df_freq = df_freq.sort_values(by="frecuencia", ascending=False)
        df_freq.to_csv("frecuencias_palabras.csv", index=False, encoding="utf-8")
        print("Frecuencias guardadas en 'frecuencias_palabras.csv'.")
    except Exception as exc:
        print(f"No se pudieron guardar las frecuencias: {exc}")

    print("\nAnálisis completado.")


if __name__ == "__main__":
    main()
