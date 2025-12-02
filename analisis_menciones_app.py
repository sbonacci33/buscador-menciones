"""Aplicación Streamlit para analizar menciones de un término en la web."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from analisis_core import (
    MAX_RESULTADOS_WEB,
    analizar_menciones_web,
    limpiar_texto,
)

st.set_page_config(page_title="Análisis de menciones", layout="wide")

# =========================
# TÍTULO E INTRODUCCIÓN
# =========================
st.title("Análisis de menciones en la web")
st.write(
    "Busca páginas en la web que mencionen un término, cuenta las veces que"
    " aparece y muestra las palabras más asociadas en los textos encontrados."
)


# =========================
# ENTRADAS DEL USUARIO
# =========================
def fechas_por_defecto() -> tuple[date, date]:
    """Rango por defecto: últimos 30 días."""

    hoy = date.today()
    return hoy - timedelta(days=30), hoy


def mostrar_formulario():
    """Muestra inputs principales en la página."""

    termino = st.text_input("Término o nombre", placeholder="Ej: Lionel Messi")

    fecha_ini_defecto, fecha_fin_defecto = fechas_por_defecto()
    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Fecha desde", value=fecha_ini_defecto)
    with col2:
        fecha_hasta = st.date_input("Fecha hasta", value=fecha_fin_defecto)

    return termino.strip(), fecha_desde, fecha_hasta


def mostrar_resumen(resumen: dict):
    """Muestra métricas resumidas del análisis."""

    st.write(
        f"Plazo analizado: {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')}"
    )
    col1, col2 = st.columns(2)
    col1.metric("Páginas con menciones", resumen.get("total_paginas_con_mencion", 0))
    col2.metric("Menciones totales del término", resumen.get("total_menciones_termino", 0))


def mostrar_tabla_paginas(df_paginas: pd.DataFrame):
    """Despliega tabla con las páginas encontradas."""

    st.subheader("Páginas encontradas")
    df_para_tabla = df_paginas.copy()
    df_para_tabla["texto_resumen"] = df_para_tabla["texto"].apply(
        lambda x: (limpiar_texto(str(x))[:200] + "...") if isinstance(x, str) else ""
    )
    st.dataframe(
        df_para_tabla[["titulo", "url", "num_menciones_termino", "texto_resumen"]],
        use_container_width=True,
    )


def mostrar_palabras(df_top_palabras: pd.DataFrame):
    """Despliega tabla y gráfico de palabras asociadas."""

    st.subheader("Palabras asociadas más frecuentes")
    if df_top_palabras.empty:
        st.info("No se encontraron palabras asociadas para este conjunto de páginas.")
        return

    st.dataframe(df_top_palabras, use_container_width=True)
    st.bar_chart(df_top_palabras.set_index("palabra"))


# =========================
# LÓGICA DE LA PÁGINA
# =========================
termino, fecha_desde, fecha_hasta = mostrar_formulario()

if st.button("Analizar"):
    if not termino:
        st.error("Por favor ingresa un término o nombre para analizar.")
    elif fecha_desde > fecha_hasta:
        st.error("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
    else:
        fecha_desde_str = fecha_desde.isoformat()
        fecha_hasta_str = fecha_hasta.isoformat()

        with st.spinner("Buscando y analizando páginas web..."):
            df_paginas, df_top_palabras, resumen = analizar_menciones_web(
                termino=termino,
                fecha_desde=fecha_desde_str,
                fecha_hasta=fecha_hasta_str,
                top_n=30,
                max_resultados_web=MAX_RESULTADOS_WEB,
            )

        if df_paginas.empty:
            st.warning("No se encontraron páginas que mencionen el término en la web.")
        else:
            mostrar_resumen(resumen)

            with st.expander("Ver páginas analizadas", expanded=True):
                mostrar_tabla_paginas(df_paginas)

            mostrar_palabras(df_top_palabras)
else:
    st.info("Ingresa los datos y presiona **Analizar** para comenzar.")
