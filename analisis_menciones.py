#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nombre de archivo sugerido: analisis_menciones.py

Instrucciones de instalación (ejecutar en la terminal):
    pip install snscrape pandas nltk unidecode
"""

# =========================
# IMPORTS NECESARIOS
# =========================
import re
from datetime import datetime
from collections import Counter

import snscrape.modules.twitter as sntwitter
import pandas as pd
import nltk
from nltk.corpus import stopwords
from unidecode import unidecode


# =========================
# UTILIDADES NLTK
# =========================
def asegurar_stopwords_espanol():
    """
    Descarga las stopwords en español de NLTK si aún no están instaladas.
    Maneja el caso en que ya estén descargadas para evitar errores.
    """
    try:
        stopwords.words("spanish")
    except LookupError:
        print("Descargando stopwords de NLTK en español...")
        nltk.download("stopwords")
    except Exception as e:
        print(f"Error al verificar/descargar stopwords de NLTK: {e}")


# =========================
# OBTENCIÓN DE TWEETS
# =========================
def obtener_tweets(termino, fecha_desde, fecha_hasta, max_tweets):
    """
    Obtiene tweets usando snscrape según un término, rango de fechas y límite de cantidad.

    Parámetros:
        termino (str): Término o nombre a buscar (por ejemplo: "Lionel Messi").
        fecha_desde (str): Fecha de inicio en formato YYYY-MM-DD.
        fecha_hasta (str): Fecha de fin en formato YYYY-MM-DD.
        max_tweets (int): Número máximo de tweets a recuperar.

    Retorna:
        pandas.DataFrame: DataFrame con columnas [fecha, usuario, contenido, url].
    """
    # Construimos la query para snscrape
    query = f'"{termino}" since:{fecha_desde} until:{fecha_hasta} lang:es'
    print(f"\nUsando la query de búsqueda: {query}")

    tweets_data = []

    try:
        scraper = sntwitter.TwitterSearchScraper(query)

        # Iteramos sobre los tweets obtenidos
        for i, tweet in enumerate(scraper.get_items()):
            if i >= max_tweets:
                break

            tweets_data.append(
                {
                    "fecha": tweet.date,  # fecha y hora del tweet
                    "usuario": tweet.user.username,  # usuario que publicó
                    "contenido": tweet.content,  # texto del tweet
                    "url": f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",  # URL del tweet
                }
            )

        df = pd.DataFrame(tweets_data)
        return df

    except Exception as e:
        print(f"Error al obtener tweets con snscrape: {e}")
        return pd.DataFrame()  # DataFrame vacío en caso de error


# =========================
# LIMPIEZA DE TEXTO
# =========================
def limpiar_texto(texto):
    """
    Limpia el texto de un tweet aplicando las reglas especificadas:
    - Minúsculas
    - Eliminar URLs
    - Eliminar menciones (@usuario) y hashtags (#tema)
    - Eliminar números
    - Eliminar signos de puntuación y caracteres especiales
    - Quitar acentos/tildes con unidecode
    - Reducir espacios múltiples a uno sólo

    Parámetros:
        texto (str): Texto original del tweet.

    Retorna:
        str: Texto limpio.
    """
    if not isinstance(texto, str):
        return ""

    # Convertir a minúsculas
    texto_limpio = texto.lower()

    # Eliminar URLs
    texto_limpio = re.sub(r"http\S+|www\.\S+", " ", texto_limpio)

    # Eliminar menciones (@usuario) y hashtags (#tema)
    texto_limpio = re.sub(r"[@#]\w+", " ", texto_limpio)

    # Eliminar números
    texto_limpio = re.sub(r"\d+", " ", texto_limpio)

    # Eliminar signos de puntuación y caracteres especiales
    # Mantener solo letras (incluyendo acentos) y espacios
    texto_limpio = re.sub(r"[^a-záéíóúüñ\s]", " ", texto_limpio)

    # Quitar acentos/tildes
    texto_limpio = unidecode(texto_limpio)

    # Reducir espacios múltiples a uno sólo
    texto_limpio = re.sub(r"\s+", " ", texto_limpio).strip()

    return texto_limpio


# =========================
# CONTEO DE PALABRAS
# =========================
def contar_palabras_frecuentes(df_tweets, termino, top_n=30):
    """
    A partir de un DataFrame de tweets, limpia los textos y calcula
    las palabras más frecuentes, excluyendo:
    - Stopwords en español (NLTK)
    - Palabras del término buscado
    - Palabras de longitud <= 2 caracteres

    Parámetros:
        df_tweets (pandas.DataFrame): DataFrame con al menos la columna 'contenido'.
        termino (str): Término original buscado (por ejemplo: "Lionel Messi").
        top_n (int): Cantidad de palabras más frecuentes a devolver.

    Retorna:
        tuple: (lista_top_n, counter_completo)
            - lista_top_n: lista de tuplas (palabra, frecuencia) con las top_n palabras.
            - counter_completo: Counter con todas las frecuencias.
    """
    if df_tweets.empty or "contenido" not in df_tweets.columns:
        return [], Counter()

    # Aseguramos que las stopwords estén disponibles
    asegurar_stopwords_espanol()
    stopwords_es = set(stopwords.words("spanish"))

    # Excluir las palabras del término buscado
    termino_limpio = limpiar_texto(termino)
    palabras_termino = set(termino_limpio.split())

    todas_las_palabras = []

    for texto in df_tweets["contenido"].dropna():
        texto_limpio = limpiar_texto(texto)

        # Ignorar textos vacíos después de la limpieza
        if not texto_limpio:
            continue

        palabras = texto_limpio.split()

        for palabra in palabras:
            # Excluir stopwords, palabras del término y palabras muy cortas
            if (
                palabra not in stopwords_es
                and palabra not in palabras_termino
                and len(palabra) > 2
            ):
                todas_las_palabras.append(palabra)

    contador = Counter(todas_las_palabras)
    top_palabras = contador.most_common(top_n)

    return top_palabras, contador


# =========================
# FUNCIÓN PRINCIPAL
# =========================
def main():
    """
    Función principal que:
    - Pide parámetros al usuario
    - Obtiene tweets con snscrape
    - Guarda tweets crudos en CSV
    - Procesa texto y calcula palabras más frecuentes
    - Muestra resultados en consola
    - Guarda frecuencias de palabras en CSV
    """

    print("=== Análisis de menciones en Twitter/X ===")

    # Solicitar datos al usuario
    termino = input("Ingrese el término o nombre a analizar (ej: Lionel Messi): ").strip()
    fecha_desde = input("Ingrese la fecha de inicio (YYYY-MM-DD): ").strip()
    fecha_hasta = input("Ingrese la fecha de fin (YYYY-MM-DD): ").strip()
    max_tweets_str = input(
        "Ingrese la cantidad máxima de tweets a obtener (ej: 500): "
    ).strip()

    # Validación básica de la cantidad de tweets
    try:
        max_tweets = int(max_tweets_str)
        if max_tweets <= 0:
            raise ValueError
    except ValueError:
        print("La cantidad máxima de tweets debe ser un número entero positivo.")
        return

    # Validación básica de fechas
    try:
        # Esto asegura que las fechas tengan formato correcto
        fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
        fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")

        if fecha_desde_dt >= fecha_hasta_dt:
            print("La fecha de inicio debe ser anterior a la fecha de fin.")
            return

        # Reconvertir a string por si se quieren usar en otro formato más adelante
        fecha_desde = fecha_desde_dt.strftime("%Y-%m-%d")
        fecha_hasta = fecha_hasta_dt.strftime("%Y-%m-%d")

    except ValueError:
        print("Las fechas deben estar en formato YYYY-MM-DD y ser válidas.")
        return

    # Obtener tweets
    print("\nObteniendo tweets... Esto puede tardar unos momentos.")
    df_tweets = obtener_tweets(termino, fecha_desde, fecha_hasta, max_tweets)

    if df_tweets.empty:
        print("No se obtuvieron tweets o ocurrió un error durante la descarga.")
        return

    # Guardar tweets crudos en CSV
    nombre_csv_tweets = "tweets_crudos.csv"
    try:
        df_tweets.to_csv(nombre_csv_tweets, index=False, encoding="utf-8")
        print(f"\nSe guardaron {len(df_tweets)} tweets en '{nombre_csv_tweets}'.")
    except Exception as e:
        print(f"Error al guardar el archivo CSV de tweets: {e}")

    # Calcular palabras más frecuentes
    print("\nProcesando texto y calculando palabras más frecuentes...")
    top_palabras, contador_completo = contar_palabras_frecuentes(df_tweets, termino, top_n=30)

    if not top_palabras:
        print("No se encontraron palabras significativas después del procesamiento.")
        return

    # Mostrar resultados en consola
    print("\n=== Top 30 palabras más frecuentes (excluyendo stopwords y el término buscado) ===")
    for palabra, frecuencia in top_palabras:
        print(f"{palabra}: {frecuencia}")

    # Guardar todas las frecuencias en CSV
    nombre_csv_frecuencias = "frecuencias_palabras.csv"
    try:
        # Crear DataFrame con todas las palabras y sus frecuencias
        df_freq = pd.DataFrame(
            list(contador_completo.items()), columns=["palabra", "frecuencia"]
        )
        # Ordenar de mayor a menor frecuencia
        df_freq = df_freq.sort_values(by="frecuencia", ascending=False)

        df_freq.to_csv(nombre_csv_frecuencias, index=False, encoding="utf-8")
        print(
            f"\nSe guardaron las frecuencias de palabras en '{nombre_csv_frecuencias}'."
        )
    except Exception as e:
        print(f"Error al guardar el archivo CSV de frecuencias: {e}")

    print("\nAnálisis completado.")


# =========================
# PUNTO DE ENTRADA
# =========================
if __name__ == "__main__":
    main()
