"""Fuentes de búsqueda web y helpers de crawling ligero.

Actualmente se usa DuckDuckGo (ddgs) como fuente principal. Se incluyen stubs
para integrar Brave, Bing, Google CSE y SerpAPI en el futuro, manteniendo la
interfaz homogénea.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS, DDGSException

USER_AGENT = "Mozilla/5.0 (compatible; BuscadorMenciones/1.0; +https://example.com)"


@dataclass
class ResultadoBusqueda:
    url: str
    titulo: str
    dominio: str
    snippet: str
    texto: str
    fuente: str = "ddg"


PROFUNDIDAD_OPCIONES = {"Rápido": 50, "Normal": 100, "Profundo": 200}


def construir_query(grupo_terminos: List[str], modo_coincidencia: str) -> str:
    """Combina términos entrecomillados. Se puede extender a operadores lógicos."""

    if modo_coincidencia == "cualquiera":
        return " OR ".join([f'"{t}"' for t in grupo_terminos])
    return " ".join([f'"{t}"' for t in grupo_terminos])


def extraer_texto_de_url(url: str, timeout: int = 10) -> str:
    """Descarga una URL y concatena el texto de sus párrafos."""

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(parrafos)
    except Exception:
        return ""


def buscar_ddg(
    grupo_terminos: List[str],
    max_resultados: int,
    modo_coincidencia: str = "frase_exacta",
    dominio_filtro: Optional[str] = None,
) -> List[ResultadoBusqueda]:
    """Busca usando ddgs y devuelve resultados con texto descargado."""

    query = construir_query(grupo_terminos, modo_coincidencia)
    resultados: List[ResultadoBusqueda] = []

    try:
        with DDGS() as buscador:
            for resultado in buscador.text(query, max_results=max_resultados, safesearch="moderate"):
                url = resultado.get("href") or resultado.get("url")
                if not url:
                    continue
                if dominio_filtro and dominio_filtro.lower() not in url.lower():
                    continue

                titulo = resultado.get("title") or ""
                snippet = resultado.get("body") or resultado.get("snippet") or ""
                dominio = urlparse(url).netloc
                texto = extraer_texto_de_url(url)

                resultados.append(
                    ResultadoBusqueda(
                        url=url,
                        titulo=titulo,
                        dominio=dominio,
                        snippet=snippet,
                        texto=texto,
                        fuente="ddg",
                    )
                )
    except DDGSException:
        return resultados
    except Exception:
        return resultados

    return resultados


# =============================
# Stubs para futuras integraciones
# =============================
def buscar_brave(*args, **kwargs) -> List[ResultadoBusqueda]:  # pragma: no cover
    """Placeholder para Brave Search API."""

    # Aquí iría la llamada real a la API de Brave usando las credenciales de config.
    return []


def buscar_bing(*args, **kwargs) -> List[ResultadoBusqueda]:  # pragma: no cover
    """Placeholder para Bing Web Search API."""

    return []


def buscar_google_cse(*args, **kwargs) -> List[ResultadoBusqueda]:  # pragma: no cover
    """Placeholder para Google Custom Search Engine."""

    return []


def buscar_serpapi(*args, **kwargs) -> List[ResultadoBusqueda]:  # pragma: no cover
    """Placeholder para SerpAPI."""

    return []


def obtener_fuente_principal() -> str:
    """Permite centralizar qué fuente se usa como principal."""

    return "ddg"


def buscar_paginas_web(
    grupo_terminos: List[str],
    profundidad: str,
    modo_coincidencia: str,
    dominio_filtro: Optional[str] = None,
) -> List[ResultadoBusqueda]:
    """Selecciona la fuente principal y ejecuta la búsqueda."""

    max_resultados = PROFUNDIDAD_OPCIONES.get(profundidad, PROFUNDIDAD_OPCIONES["Normal"])
    fuente = obtener_fuente_principal()
    if fuente == "ddg":
        return buscar_ddg(grupo_terminos, max_resultados, modo_coincidencia, dominio_filtro)
    return []
