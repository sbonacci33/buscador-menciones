"""Tablero Streamlit para monitorear menciones en la web."""
from __future__ import annotations

from datetime import date
from typing import List
import io

import pandas as pd
import streamlit as st

try:
    from analisis_core import (
        PROFUNDIDAD_OPCIONES,
        analizar_menciones_web,
        contar_bigramas,
    )
except ModuleNotFoundError as exc:
    st.set_page_config(page_title="Monitoreo de menciones", layout="wide")
    st.error(
        "No se encontró una dependencia necesaria (por ejemplo, SQLAlchemy). "
        "Ejecuta `pip install -r requirements.txt` en tu entorno virtual y vuelve a cargar la app."
    )
    st.stop()

st.set_page_config(page_title="Monitoreo de menciones", layout="wide")

MODO_COINCIDENCIA_UI = {
    "Frase exacta": "frase_exacta",
    "Todas las palabras": "todas_las_palabras",
    "Cualquiera": "cualquiera",
}


def _generar_pdf_simple(resumen: dict, df_paginas: pd.DataFrame) -> io.BytesIO:
    """Genera un PDF básico con fpdf si está disponible; si no, devuelve texto plano."""

    buffer = io.BytesIO()
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Reporte de menciones", ln=1, align="C")
        pdf.multi_cell(0, 10, txt=f"Términos: {', '.join(resumen.get('terminos', []))}")
        pdf.multi_cell(
            0,
            10,
            txt=(
                f"Total resultados: {resumen.get('total_paginas_consultadas', 0)} | "
                f"En rango: {resumen.get('paginas_en_rango_fecha', 0)} | "
                f"Sin fecha: {resumen.get('paginas_sin_fecha', 0)}"
            ),
        )
        pdf.multi_cell(0, 10, txt=f"Rango fechas: {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')}")
        pdf.multi_cell(0, 10, txt=f"Dominios top: {resumen.get('dominios_top', {})}")
        pdf.ln(5)
        pdf.multi_cell(0, 10, txt="Páginas más relevantes:")
        for _, fila in df_paginas.head(10).iterrows():
            pdf.multi_cell(
                0, 8, txt=f"- {fila.get('titulo', '')} ({fila.get('dominio', '')}) [{fila.get('fecha_publicacion', '')}]"
            )
        pdf.output(buffer)
    except Exception:
        buffer.write(
            (
                "Reporte de menciones\n"
                f"Términos: {', '.join(resumen.get('terminos', []))}\n"
                f"Total resultados: {resumen.get('total_paginas_consultadas', 0)}\n"
            ).encode("utf-8")
        )
    buffer.seek(0)
    return buffer


def _mostrar_kpis(resumen: dict):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Resultados totales", resumen.get("total_paginas_consultadas", 0))
    col2.metric("Dentro de rango", resumen.get("paginas_en_rango_fecha", 0))
    col3.metric("Sin fecha", resumen.get("paginas_sin_fecha", 0))
    col4.metric("Menciones totales", resumen.get("menciones_totales_grupo", 0))

    st.caption(
        f"Profundidad {resumen.get('profundidad')} (hasta {resumen.get('max_resultados_muestra', 0)} páginas). "
        "Una profundidad mayor puede tardar más porque se activa más crawling."
    )


def _mostrar_detalle_resumen(resumen: dict):
    st.markdown(
        f"**Plazo analizado:** {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')}"
    )
    st.markdown(
        f"**Páginas antes del filtro por fecha:** {resumen.get('paginas_antes_filtro_fecha', 0)}"
        f" | **Después del filtro:** {resumen.get('paginas_despues_filtro_fecha', 0)}"
    )
    if resumen.get("paginas_sin_fecha"):
        st.info(
            f"{resumen.get('paginas_sin_fecha')} páginas no tenían fecha detectable y se marcaron como 'Desconocida'."
        )
    if resumen.get("paginas_excluidas_por_fecha"):
        st.warning(
            f"{resumen.get('paginas_excluidas_por_fecha')} páginas quedaron fuera del rango por fecha de publicación."
        )
    st.markdown(
        f"**Fecha más antigua:** {resumen.get('fecha_mas_antigua')} | "
        f"**Más reciente:** {resumen.get('fecha_mas_reciente')}"
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
        f"**Dominio filtrado:** {resumen.get('dominio_filtro') or 'Sin filtro'}  "
        f"**Profundidad:** {resumen.get('profundidad')} ({resumen.get('max_resultados_muestra')} resultados)"
    )
    st.caption(
        "Se analiza una muestra de resultados iniciales devueltos por DuckDuckGo. "
        "No pretende cubrir la web completa."
    )


def _mostrar_tabla_paginas(df_paginas: pd.DataFrame):
    columnas_menciones = [c for c in df_paginas.columns if c.startswith("menciones_termino_")]
    columnas = [
        "fecha_publicacion",
        "titulo",
        "dominio",
        "url",
        "termino_encontrado",
        "palabras_clave_asociadas",
        "puntaje_relevancia",
        "menciones_totales_pagina",
        *columnas_menciones,
    ]
    df_para_tabla = df_paginas[columnas].copy()
    df_para_tabla["fecha_publicacion"] = df_para_tabla["fecha_publicacion"].fillna("Desconocida")
    st.dataframe(
        df_para_tabla,
        use_container_width=True,
        column_config={"url": st.column_config.LinkColumn("URL")},
    )


def _filtros_tab_paginas(df_paginas: pd.DataFrame) -> pd.DataFrame:
    filtro_dominio_contiene = st.text_input("Filtrar dominios que contengan", "")
    min_menciones = st.slider(
        "Menciones mínimas en página", 0, int(df_paginas["menciones_totales_pagina"].max()), value=0
    )

    df_filtrado = df_paginas.copy()
    if filtro_dominio_contiene:
        df_filtrado = df_filtrado[df_filtrado["dominio"].str.contains(filtro_dominio_contiene, case=False, na=False)]
    df_filtrado = df_filtrado[df_filtrado["menciones_totales_pagina"] >= min_menciones]
    return df_filtrado


def _reiniciar_consulta() -> None:
    """Limpia el estado de la aplicación y recarga la página."""

    for key in list(st.session_state.keys()):
        st.session_state.pop(key)
    st.rerun()


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

    profundidad = st.slider(
        "Profundidad de búsqueda (1=rápido, 5=profundo)", 1, 5, value=3,
        help="Profundidades altas activan crawling extendido y pueden demorar más."
    )
    modo_coincidencia_label = st.selectbox("Modo de coincidencia", list(MODO_COINCIDENCIA_UI.keys()), index=0)
    dominio_filtro = st.text_input("Filtrar por dominio (opcional)", help="Ej: clarin.com o .com.ar")
    incluir_sin_fecha = st.checkbox(
        "Incluir páginas sin fecha detectada", value=True,
        help="Si se desactiva, solo se mostrarán páginas con fecha de publicación identificada."
    )
    top_n_palabras = st.slider("Top palabras asociadas", 10, 50, value=30, step=5)
    crawl_extendido = st.checkbox(
        "Activar crawl extendido", value=False,
        help="Explora enlaces secundarios hasta 3 saltos. Puede tardar más."
    )

    boton_analizar = st.button("Analizar", type="primary")
    st.button("🔄 Realizar nueva búsqueda", on_click=_reiniciar_consulta)


st.title("Tablero de análisis de menciones en la web")
st.caption(
    "Explora menciones de hasta cinco términos sobre una muestra de resultados. "
    "La app usa DuckDuckGo (ddgs), intenta detectar la fecha de publicación real y analiza solo la cantidad de resultados indicada en la profundidad seleccionada."
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
                incluir_paginas_sin_fecha=incluir_sin_fecha,
                top_n_palabras=top_n_palabras,
                crawl_extendido=crawl_extendido,
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

                st.markdown("### Distribución temporal")
                fechas_conocidas = df_paginas[df_paginas["fecha_publicacion"] != "sin_fecha"]
                if not fechas_conocidas.empty:
                    hist_data = (
                        fechas_conocidas.groupby("fecha_publicacion")[["url"]]
                        .count()
                        .rename(columns={"url": "frecuencia"})
                    )
                    st.bar_chart(hist_data)
                else:
                    st.caption("No se detectaron fechas en los resultados.")

            with tab_palabras:
                st.subheader("Palabras asociadas")
                if df_top_palabras.empty:
                    st.info("No se encontraron palabras asociadas en la muestra analizada.")
                else:
                    st.dataframe(df_top_palabras, use_container_width=True)
                    st.bar_chart(df_top_palabras.set_index("palabra"))
                    st.caption("Nube de palabras (tamaño ~ frecuencia)")
                    try:
                        from wordcloud import WordCloud
                        import matplotlib.pyplot as plt

                        wc = WordCloud(width=800, height=400, background_color="white")
                        wc.generate_from_frequencies(
                            {row.palabra: row.frecuencia for row in df_top_palabras.itertuples()}
                        )
                        fig, ax = plt.subplots()
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        st.pyplot(fig)
                    except Exception:
                        st.caption("Instala 'wordcloud' para ver la nube de palabras.")

                st.markdown("---")
                st.subheader("Bigramas frecuentes (experimental)")
                if df_top_bigramas.empty:
                    st.caption("No hay suficientes textos para generar bigramas.")
                else:
                    st.dataframe(df_top_bigramas, use_container_width=True)
                    st.bar_chart(df_top_bigramas.set_index("bigram"))

            with tab_paginas:
                st.subheader("Detalle de páginas")
                st.caption("El filtro de fechas se aplica sobre la fecha de publicación detectada en cada página.")
                df_filtrado = _filtros_tab_paginas(df_paginas)
                _mostrar_tabla_paginas(df_filtrado)

                csv_paginas = df_filtrado.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar páginas (CSV)", data=csv_paginas, file_name="paginas_menciones.csv")
                st.download_button(
                    "Descargar páginas (JSON)", data=df_filtrado.to_json(orient="records"), file_name="paginas_menciones.json"
                )
                pdf_buffer = _generar_pdf_simple(resumen, df_filtrado)
                st.download_button(
                    "Descargar reporte (PDF)",
                    data=pdf_buffer,
                    file_name="reporte_menciones.pdf",
                    mime="application/pdf",
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
                st.markdown(
                    f"**Filtro por fecha:** {resumen.get('fecha_desde')} a {resumen.get('fecha_hasta')} (basado en fecha de publicación detectada)"
                )
                st.markdown(
                    f"**Páginas sin fecha incluida:** {'Sí' if resumen.get('incluye_paginas_sin_fecha') else 'No'}"
                )
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
