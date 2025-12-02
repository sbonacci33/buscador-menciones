"""Aplicación web en Streamlit para analizar menciones en la web."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from analisis_core import analizar_menciones_web, limpiar_texto

st.set_page_config(page_title="Análisis de menciones", layout="wide")

# =========================
# CONFIGURACIÓN DE LA PÁGINA
# =========================
st.title("Análisis de menciones en la web")
st.write(
    "Carga resultados de DuckDuckGo y calcula cuántas veces aparece tu término"
    " en las páginas encontradas. El filtro por fecha es aproximado porque la"
    " API de búsqueda no expone un rango exacto."
)

# =========================
# ENTRADAS DEL USUARIO
# =========================
def fecha_por_defecto() -> tuple[date, date]:
    """Devuelve un rango de fechas por defecto (últimos 30 días)."""

    hoy = date.today()
    return hoy - timedelta(days=30), hoy


def mostrar_formulario():
    """Muestra el formulario de parámetros en la barra lateral."""

    st.sidebar.header("Parámetros de búsqueda")
    termino = st.sidebar.text_input(
        "Término o nombre a analizar", placeholder="Ej: Lionel Messi"
    )

    fecha_ini_defecto, fecha_fin_defecto = fecha_por_defecto()
    fecha_inicio = st.sidebar.date_input("Fecha de inicio", value=fecha_ini_defecto)
    fecha_fin = st.sidebar.date_input("Fecha de fin", value=fecha_fin_defecto)

    max_resultados = st.sidebar.number_input(
        "Máximo de resultados web", min_value=1, max_value=200, value=50
    )

    incluir_redes = st.sidebar.checkbox(
        "Incluir redes sociales (no implementado)", value=False
    )

    return termino, fecha_inicio, fecha_fin, int(max_resultados), incluir_redes


termino, fecha_inicio, fecha_fin, max_resultados, incluir_redes = mostrar_formulario()

if incluir_redes:
    st.info("La opción de redes sociales está planificada pero aún no se implementa.")

# =========================
# BOTÓN DE ACCIÓN
# =========================
if st.button("Analizar"):
    termino = termino.strip()
    if not termino:
        st.error("Por favor ingresa un término o nombre para analizar.")
    elif fecha_inicio > fecha_fin:
        st.error("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
    else:
        fecha_inicio_str = fecha_inicio.isoformat()
        fecha_fin_str = fecha_fin.isoformat()

        with st.spinner("Buscando y analizando páginas web..."):
            df_paginas, df_frecuencias, resumen = analizar_menciones_web(
                termino=termino,
                fecha_desde=fecha_inicio_str,
                fecha_hasta=fecha_fin_str,
                max_resultados_web=max_resultados,
                top_n=30,
            )

        if df_paginas.empty:
            st.warning(
                "No se encontraron páginas que mencionen el término en la web."
            )
        else:
            st.success("Análisis completado.")

            # =========================
            # MÉTRICAS RESUMIDAS
            # =========================
            col1, col2, col3 = st.columns(3)
            col1.metric("Páginas consultadas", resumen.get("total_paginas_consultadas", 0))
            col2.metric("Páginas con menciones", resumen.get("total_paginas_con_menciones", 0))
            col3.metric("Menciones totales del término", resumen.get("total_menciones_termino", 0))

            # =========================
            # TABLA DE PÁGINAS
            # =========================
            st.subheader("Páginas encontradas")
            df_para_tabla = df_paginas.copy()
            df_para_tabla["texto_resumen"] = df_para_tabla["texto"].apply(
                lambda x: (limpiar_texto(str(x))[:200] + "...") if isinstance(x, str) else ""
            )
            st.dataframe(
                df_para_tabla[
                    ["titulo", "url", "num_menciones_termino", "texto_resumen"]
                ],
                use_container_width=True,
            )

            csv_paginas = df_paginas.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar CSV de páginas",
                data=csv_paginas,
                file_name="paginas_web.csv",
                mime="text/csv",
            )

            # =========================
            # FRECUENCIAS DE PALABRAS
            # =========================
            st.subheader("Palabras más frecuentes")
            if not df_frecuencias.empty:
                st.dataframe(df_frecuencias, use_container_width=True)
                st.bar_chart(df_frecuencias.set_index("palabra"))

                csv_frecuencias = df_frecuencias.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Descargar CSV de frecuencias",
                    data=csv_frecuencias,
                    file_name="frecuencias_palabras.csv",
                    mime="text/csv",
                )
            else:
                st.info(
                    "No se encontraron palabras frecuentes (revisa el término o aumenta el número de resultados)."
                )

else:
    st.info("Completa los datos y presiona **Analizar** para comenzar.")
