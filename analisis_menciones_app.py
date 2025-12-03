"""Tablero Streamlit para monitorear menciones en la web."""
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

st.set_page_config(page_title="Monitoreo de menciones", layout="wide")

MODO_COINCIDENCIA_UI = {
    "Frase exacta": "frase_exacta",
    "Todas las palabras": "todas_las_palabras",
    "Cualquiera": "cualquiera",
}


def _formatear_url_clickable(url: str) -> str:
    return f"[Abrir enlace]({url})"


def _mostrar_kpis(resumen: dict):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Páginas con menciones", resumen.get("paginas_con_menciones", 0))
    col2.metric("Menciones totales", resumen.get("menciones_totales_grupo", 0))
    profundidad = resumen.get("profundidad", "")
    max_resultados = resumen.get("max_resultados_muestra", 0)
    col3.metric("Profundidad usada", f"{profundidad} ({max_resultados} resultados)")
    col4.metric(
        "Promedio menciones/página", f"{resumen.get('promedio_menciones_por_pagina', 0):.2f}"
    )


def _mostrar_detalle_resumen(resumen: dict):
    st.markdown(
        f"**Plazo analizado:** {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')}"
    )
    st.markdown(
        "**Términos analizados:** " + ", ".join([f"`{t}`" for t in resumen.get("terminos", [])])
    )
    st.markdown(
        "**Menciones por término:**\n" + "\n".join(
            [f"• {t}: {v}" for t, v in resumen.get("menciones_por_termino", {}).items()]
        )
    )
    st.markdown(
        f"**Modo de coincidencia:** {resumen.get('modo_coincidencia')}  "
        f"**Dominio filtrado:** {resumen.get('dominio_filtro') or 'Sin filtro'}"
    )
    st.caption(
        "Se analiza una muestra de resultados iniciales devueltos por DuckDuckGo. "
        "No pretende cubrir la web completa."
    )


def _mostrar_tabla_paginas(df_paginas: pd.DataFrame):
    columnas_menciones = [c for c in df_paginas.columns if c.startswith("menciones_termino_")]
    columnas = ["titulo", "dominio", "url", "menciones_totales_pagina", *columnas_menciones]
    df_para_tabla = df_paginas[columnas].copy()
    df_para_tabla["url"] = df_para_tabla["url"].apply(_formatear_url_clickable)
    st.dataframe(
        df_para_tabla,
        use_container_width=True,
        column_config={"url": st.column_config.LinkColumn("URL")},
    )


def _filtros_tab_paginas(df_paginas: pd.DataFrame) -> pd.DataFrame:
    dominios = sorted(df_paginas["dominio"].dropna().unique().tolist())
    dominio_sel = st.multiselect("Filtrar por dominio", dominios)
    min_menciones = st.slider(
        "Menciones mínimas en página", 0, int(df_paginas["menciones_totales_pagina"].max()), value=0
    )

    df_filtrado = df_paginas.copy()
    if dominio_sel:
        df_filtrado = df_filtrado[df_filtrado["dominio"].isin(dominio_sel)]
    df_filtrado = df_filtrado[df_filtrado["menciones_totales_pagina"] >= min_menciones]
    return df_filtrado


with st.sidebar:
    st.header("Configuración")
    st.caption("Define los términos y el alcance del muestreo. Analizamos los primeros resultados.")

    terminos_input = [
        st.text_input("Término o nombre 1 (obligatorio)"),
        st.text_input("Término o nombre 2"),
        st.text_input("Término o nombre 3"),
        st.text_input("Término o nombre 4"),
        st.text_input("Término o nombre 5"),
    ]

    fecha_hoy = date.today()
    fecha_desde = st.date_input("Fecha desde", value=fecha_hoy)
    fecha_hasta = st.date_input("Fecha hasta", value=fecha_hoy)

    profundidad = st.selectbox("Profundidad de búsqueda", list(PROFUNDIDAD_OPCIONES.keys()), index=1)
    modo_coincidencia_label = st.selectbox("Modo de coincidencia", list(MODO_COINCIDENCIA_UI.keys()), index=0)
    dominio_filtro = st.text_input("Filtrar por dominio (opcional)", help="Ej: clarin.com o .com.ar")
    top_n_palabras = st.slider("Top palabras asociadas", 10, 50, value=30, step=5)

    boton_analizar = st.button("Analizar", type="primary")


st.title("Tablero de análisis de menciones en la web")
st.caption(
    "Explora menciones de hasta cinco términos sobre una muestra de resultados. "
    "La app usa DuckDuckGo (ddgs) y analiza solo la cantidad de resultados indicada en la profundidad seleccionada."
)

if not boton_analizar:
    st.info(
        "Completa los filtros en la barra lateral y pulsa **Analizar** para generar el tablero."
    )
else:
    grupo_terminos: List[str] = [t.strip() for t in terminos_input if t and t.strip()][:5]

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
                "No se encontraron páginas con menciones para los términos y filtros seleccionados en la muestra analizada."
            )
        else:
            tab_resumen, tab_palabras, tab_paginas, tab_dominios, tab_config = st.tabs(
                ["Resumen", "Palabras asociadas", "Páginas", "Dominios", "Configuración / Ayuda"]
            )

            with tab_resumen:
                _mostrar_kpis(resumen)
                st.markdown("---")
                _mostrar_detalle_resumen(resumen)

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
                st.subheader("Bigramas frecuentes (experimental)")
                if df_top_bigramas.empty:
                    st.caption("No hay suficientes textos para generar bigramas.")
                else:
                    st.dataframe(df_top_bigramas, use_container_width=True)
                    st.bar_chart(df_top_bigramas.set_index("bigram"))

            with tab_paginas:
                st.subheader("Detalle de páginas")
                df_filtrado = _filtros_tab_paginas(df_paginas)
                _mostrar_tabla_paginas(df_filtrado)

                csv_paginas = df_filtrado.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar páginas (CSV)", data=csv_paginas, file_name="paginas_menciones.csv")
                st.download_button(
                    "Descargar páginas (JSON)", data=df_filtrado.to_json(orient="records"), file_name="paginas_menciones.json"
                )

            with tab_dominios:
                st.subheader("Dominios más frecuentes")
                dominios_df = (
                    df_paginas.groupby("dominio")
                    .agg(paginas=("url", "count"), menciones=("menciones_totales_pagina", "sum"))
                    .reset_index()
                    .sort_values(by="paginas", ascending=False)
                )
                st.dataframe(dominios_df, use_container_width=True)
                st.bar_chart(dominios_df.set_index("dominio")[["paginas"]])

            with tab_config:
                st.subheader("Configuración aplicada y ayuda")
                st.markdown(
                    f"**Profundidad:** {profundidad} ({resumen.get('max_resultados_muestra')} resultados)"
                )
                st.markdown(f"**Modo de coincidencia:** {modo_coincidencia_label}")
                st.markdown(f"**Dominio filtrado:** {dominio_filtro if dominio_filtro else 'Sin filtro'}")
                st.markdown("**Selección de páginas:** se muestran las páginas con más menciones en la muestra consultada.")
                st.markdown(
                    "**Qué significan los modos:**\n"
                    "- *Frase exacta*: busca la frase completa como aparece.\n"
                    "- *Todas las palabras*: la página debe contener todas las palabras del término.\n"
                    "- *Cualquiera*: cuenta si aparece alguna palabra del término."
                )
                st.caption(
                    "La aplicación utiliza ddgs (DuckDuckGo) y solo procesa la muestra definida por la profundidad seleccionada."
                )
