"""Aplicación Streamlit para analizar menciones de términos en la web."""

from __future__ import annotations

from datetime import date
from typing import List

import pandas as pd
import streamlit as st

from analisis_core import (
    PROFUNDIDAD_OPCIONES,
    analizar_menciones_web,
    contar_bigramas,
)

st.set_page_config(page_title="Análisis de menciones en la web", layout="wide")

# Mapeo de etiquetas visibles a valores internos
MODO_COINCIDENCIA_UI = {
    "Frase exacta": "frase_exacta",
    "Todas las palabras": "todas_las_palabras",
    "Cualquiera de las palabras": "cualquiera",
}


# =========================
# FUNCIONES DE APOYO
# =========================
def _formatear_url_clickable(url: str) -> str:
    return f"[Abrir enlace]({url})"


def _mostrar_kpis(resumen: dict):
    """Fila de KPIs clave del análisis."""

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Páginas con menciones", resumen.get("paginas_con_menciones", 0))
    col2.metric("Menciones totales", resumen.get("menciones_totales_grupo", 0))
    profundidad = resumen.get("profundidad", "")
    max_resultados = resumen.get("max_resultados_muestra", 0)
    col3.metric("Profundidad usada", f"{profundidad} ({max_resultados} resultados)")
    col4.metric(
        "Promedio menciones/página",
        f"{resumen.get('promedio_menciones_por_pagina', 0):.2f}",
    )


def _mostrar_detalle_resumen(resumen: dict):
    st.markdown(
        f"**Plazo analizado:** {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')}"
    )
    st.markdown(
        "**Términos analizados:** "
        + ", ".join([f"`{t}`" for t in resumen.get("terminos", [])])
    )
    st.markdown(
        "**Menciones por término:**\n" + "\n".join(
            [f"• {t}: {v}" for t, v in resumen.get("menciones_por_termino", {}).items()]
        )
    )
    st.markdown(
        f"**Modo de coincidencia:** {resumen.get('modo_coincidencia')}\n"
        f"**Dominio filtrado:** {resumen.get('dominio_filtro') or 'Sin filtro'}"
    )
    st.caption(
        "Recuerda: se analiza una muestra de los primeros resultados devueltos "
        "por DuckDuckGo (ddgs). No es un recuento exhaustivo de toda la web."
    )


# =========================
# SIDEBAR DE PARÁMETROS
# =========================
with st.sidebar:
    st.header("Configuración")
    st.caption(
        "Define los términos y el alcance del muestreo. Se analizan únicamente "
        "los primeros resultados devueltos por el buscador."
    )
    termino_1 = st.text_input("Término o nombre 1 (obligatorio)")
    termino_2 = st.text_input("Término o nombre 2 (opcional)")
    termino_3 = st.text_input("Término o nombre 3 (opcional)")

    fecha_hoy = date.today()
    fecha_desde = st.date_input("Fecha desde", value=fecha_hoy)
    fecha_hasta = st.date_input("Fecha hasta", value=fecha_hoy)

    profundidad = st.selectbox("Profundidad de búsqueda", list(PROFUNDIDAD_OPCIONES.keys()))
    modo_coincidencia_label = st.selectbox(
        "Modo de coincidencia",
        list(MODO_COINCIDENCIA_UI.keys()),
        index=0,
        help=(
            "Define cómo se cuentan las apariciones de cada término: Frase exacta, "
            "todas las palabras presentes o cualquier palabra del término."
        ),
    )
    dominio_filtro = st.text_input(
        "Filtrar por dominio (opcional)",
        help="Ejemplo: clarin.com o lanacion.com.ar. Dejar vacío para no filtrar.",
    )
    top_n_palabras = st.slider("Top palabras asociadas", 10, 50, value=30, step=5)

    boton_analizar = st.button("Analizar", type="primary")


# =========================
# CUERPO PRINCIPAL
# =========================
st.title("Análisis de menciones en la web")
st.caption(
    "Explora menciones de hasta tres términos sobre una muestra de resultados. "
    "La app usa DuckDuckGo (ddgs) y analiza solo la cantidad de resultados "
    "indicada en la profundidad seleccionada."
)

if not boton_analizar:
    st.info(
        "Completa los filtros en la barra lateral y pulsa **Analizar** para generar "
        "el tablero. Recuerda que el análisis se basa en una muestra, no en toda la web."
    )
else:
    grupo_terminos: List[str] = [
        t.strip() for t in [termino_1, termino_2, termino_3] if t and t.strip()
    ][:3]

    errores: List[str] = []
    if not grupo_terminos:
        errores.append("Debes ingresar al menos un término (el primero es obligatorio).")
    if fecha_desde > fecha_hasta:
        errores.append("La fecha de inicio debe ser anterior o igual a la fecha de fin.")

    if errores:
        for error in errores:
            st.error(error)
    else:
        modo_coincidencia = MODO_COINCIDENCIA_UI[modo_coincidencia_label]
        fecha_desde_str, fecha_hasta_str = fecha_desde.isoformat(), fecha_hasta.isoformat()

        with st.spinner("Buscando y analizando páginas web en la muestra seleccionada..."):
            df_paginas, df_top_palabras, resumen = analizar_menciones_web(
                grupo_terminos=grupo_terminos,
                fecha_desde=fecha_desde_str,
                fecha_hasta=fecha_hasta_str,
                profundidad=profundidad,
                modo_coincidencia=modo_coincidencia,
                dominio_filtro=dominio_filtro.strip() or None,
                top_n_palabras=top_n_palabras,
            )

            df_top_bigramas = contar_bigramas(df_paginas, grupo_terminos, top_n=15)

        if df_paginas.empty:
            st.warning(
                "No se encontraron páginas con menciones para los términos y filtros "
                "seleccionados en la muestra analizada."
            )
        else:
            tab_resumen, tab_palabras, tab_paginas, tab_config = st.tabs(
                ["Resumen", "Palabras asociadas", "Páginas", "Configuración avanzada"]
            )

            with tab_resumen:
                _mostrar_kpis(resumen)
                st.markdown("---")
                _mostrar_detalle_resumen(resumen)

                if len(grupo_terminos) > 1:
                    menciones_data = pd.DataFrame(
                        {
                            "término": list(resumen["menciones_por_termino"].keys()),
                            "menciones": list(resumen["menciones_por_termino"].values()),
                        }
                    )
                    st.bar_chart(menciones_data.set_index("término"))

            with tab_palabras:
                st.subheader("Palabras asociadas")
                if df_top_palabras.empty:
                    st.info("No se encontraron palabras asociadas en la muestra analizada.")
                else:
                    st.dataframe(df_top_palabras, use_container_width=True)
                    st.bar_chart(df_top_palabras.set_index("palabra"))

                st.markdown("---")
                st.subheader("Bigramas frecuentes (opcional)")
                if df_top_bigramas.empty:
                    st.caption("No hay suficientes textos para generar bigramas.")
                else:
                    st.dataframe(df_top_bigramas, use_container_width=True)
                    st.bar_chart(df_top_bigramas.set_index("bigram"))

            with tab_paginas:
                st.subheader("Detalle de páginas")
                columnas_menciones = [
                    c for c in df_paginas.columns if c.startswith("menciones_termino_")
                ]
                columnas = ["titulo", "url", "menciones_totales_pagina", *columnas_menciones]
                df_para_tabla = df_paginas[columnas].copy()
                df_para_tabla["url"] = df_para_tabla["url"].apply(_formatear_url_clickable)
                st.dataframe(
                    df_para_tabla,
                    use_container_width=True,
                    column_config={"url": st.column_config.LinkColumn("URL")},
                )

                csv_paginas = df_paginas.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Descargar páginas (CSV)",
                    data=csv_paginas,
                    file_name="paginas_menciones.csv",
                    mime="text/csv",
                )

            with tab_config:
                st.subheader("Configuración aplicada")
                st.markdown(
                    f"**Profundidad:** {profundidad} ({resumen.get('max_resultados_muestra')} resultados)"
                )
                st.markdown(f"**Modo de coincidencia:** {modo_coincidencia_label}")
                st.markdown(
                    f"**Dominio filtrado:** {dominio_filtro if dominio_filtro else 'Sin filtro'}"
                )
                st.markdown(
                    "**Qué significan los modos:**\n"
                    "- *Frase exacta*: busca la frase completa como aparece.\n"
                    "- *Todas las palabras*: la página debe contener todas las palabras del término.\n"
                    "- *Cualquiera de las palabras*: cuenta si aparece alguna palabra del término."
                )
                st.caption(
                    "La aplicación utiliza ddgs (DuckDuckGo) y solo procesa la muestra "
                    "definida por la profundidad seleccionada. No pretende cubrir la web completa."
                )
