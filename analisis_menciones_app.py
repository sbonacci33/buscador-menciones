"""Aplicación Streamlit para analizar menciones de uno o varios términos en la web."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from analisis_core import MAX_RESULTADOS_WEB, analizar_menciones_web

st.set_page_config(page_title="Análisis de menciones", layout="wide")

# =========================
# TÍTULO E INTRODUCCIÓN
# =========================
st.title("Análisis de menciones en la web")
st.write(
    "Busca páginas en la web que mencionen uno o varios términos, cuenta las "
    "veces que aparecen y muestra palabras asociadas en los textos encontrados."
)
st.caption(
    "Los resultados se basan en una muestra de los primeros "
    f"{MAX_RESULTADOS_WEB} resultados devueltos por el motor de búsqueda (ddgs)."
)


# =========================
# ENTRADAS DEL USUARIO
# =========================
def mostrar_formulario():
    """Inputs principales (términos y fechas)."""

    st.subheader("Parámetros de búsqueda")
    termino_1 = st.text_input("Término o nombre 1 (obligatorio)")
    termino_2 = st.text_input("Término o nombre 2 (opcional)")
    termino_3 = st.text_input("Término o nombre 3 (opcional)")

    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Fecha desde", value=date.today())
    with col2:
        fecha_hasta = st.date_input("Fecha hasta", value=date.today())

    return termino_1, termino_2, termino_3, fecha_desde, fecha_hasta


def validar_entradas(
    grupo_terminos: list[str], fecha_desde: date, fecha_hasta: date
) -> list[str]:
    """Valida términos y rango de fechas. Devuelve lista de errores."""

    errores: list[str] = []
    if not grupo_terminos:
        errores.append("Debes ingresar al menos un término (el primero es obligatorio).")
    if fecha_desde > fecha_hasta:
        errores.append("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
    return errores


# =========================
# BLOQUES DE VISUALIZACIÓN
# =========================
def mostrar_resumen(resumen: dict):
    """Muestra las estadísticas principales en texto para claridad."""

    st.subheader("Estadísticas del análisis")
    st.markdown(
        f"Plazo analizado: **{resumen.get('fecha_desde')}** a **{resumen.get('fecha_hasta')}**"
    )
    st.markdown(
        "Términos analizados: "
        + ", ".join([f"**{t}**" for t in resumen.get("terminos", [])])
    )
    st.markdown(
        f"Páginas con menciones: **{resumen.get('paginas_con_menciones', 0)}**"
    )
    st.markdown(
        "Menciones totales del grupo: "
        f"**{resumen.get('menciones_totales_grupo', 0)}**"
    )
    st.markdown(
        "Promedio de menciones por página con mención: "
        f"**{resumen.get('promedio_menciones_por_pagina', 0):.2f}**"
    )

    st.markdown("**Menciones por término:**")
    for termino, cantidad in resumen.get("menciones_por_termino", {}).items():
        st.markdown(f"• {termino}: {cantidad} menciones")


def mostrar_tabla_paginas(df_paginas: pd.DataFrame):
    """Despliega la tabla de páginas sin la columna de texto completo."""

    st.subheader("Páginas encontradas")
    columnas_menciones = [c for c in df_paginas.columns if c.startswith("menciones_termino_")]
    columnas = ["titulo", "url", "menciones_totales_pagina", *columnas_menciones]
    st.dataframe(df_paginas[columnas], use_container_width=True)


def mostrar_palabras(df_top_palabras: pd.DataFrame):
    """Tabla y gráfico de palabras asociadas."""

    st.subheader("Palabras asociadas más frecuentes")
    if df_top_palabras.empty:
        st.info("No se encontraron palabras asociadas para estas páginas.")
        return

    st.dataframe(df_top_palabras, use_container_width=True)
    st.bar_chart(df_top_palabras.set_index("palabra"))


# =========================
# FLUJO PRINCIPAL DE LA APP
# =========================
termino_1, termino_2, termino_3, fecha_desde, fecha_hasta = mostrar_formulario()

if st.button("Analizar"):
    grupo_terminos = [t.strip() for t in [termino_1, termino_2, termino_3] if t.strip()]
    errores = validar_entradas(grupo_terminos, fecha_desde, fecha_hasta)

    if errores:
        for error in errores:
            st.error(error)
    else:
        fecha_desde_str = fecha_desde.isoformat()
        fecha_hasta_str = fecha_hasta.isoformat()

        with st.spinner("Buscando y analizando páginas web..."):
            df_paginas, df_top_palabras, resumen = analizar_menciones_web(
                grupo_terminos=grupo_terminos,
                fecha_desde=fecha_desde_str,
                fecha_hasta=fecha_hasta_str,
                top_n=30,
                max_resultados=MAX_RESULTADOS_WEB,
            )

        if df_paginas.empty:
            st.warning(
                "No se encontraron páginas que mencionen los términos en la muestra "
                "de resultados analizada."
            )
        else:
            mostrar_resumen(resumen)
            mostrar_tabla_paginas(df_paginas)
            mostrar_palabras(df_top_palabras)
else:
    st.info("Ingresa los datos y presiona **Analizar** para comenzar.")
