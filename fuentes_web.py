"""Fuentes de búsqueda web y helpers de crawling ligero.

Actualmente se usa DuckDuckGo (ddgs) como fuente principal. Se incluyen stubs
para integrar Brave, Bing, Google CSE y SerpAPI en el futuro, manteniendo la
interfaz homogénea.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from ddgs import DDGS

from config import settings

USER_AGENT = "Mozilla/5.0 (compatible; BuscadorMenciones/1.0; +https://example.com)"


@dataclass
class ResultadoBusqueda:
    url: str
    titulo: str
    dominio: str
    snippet: str
    texto: str
    fecha_publicacion: Optional[str]
    canonica: Optional[str] = None
    fuente: str = "ddg"
    profundidad: int = 1


PROFUNDIDAD_OPCIONES = {1: 60, 2: 120, 3: 180, 4: 240, 5: 300}


def construir_query(grupo_terminos: List[str], modo_coincidencia: str) -> str:
    """Combina términos entrecomillados. Se puede extender a operadores lógicos."""

    if modo_coincidencia == "cualquiera":
        return " OR ".join([f'"{t}"' for t in grupo_terminos])
    return " ".join([f'"{t}"' for t in grupo_terminos])


def _parsear_fecha(fecha_str: str) -> Optional[str]:
    try:
        fecha = parser.parse(fecha_str)
        return fecha.date().isoformat()
    except Exception:
        return None


def extraer_fecha_publicacion(soup: BeautifulSoup) -> Optional[str]:
    """Intenta encontrar la fecha de publicación a través de múltiples formatos."""

    meta_props = [
        ("property", "article:published_time"),
        ("property", "og:published_time"),
        ("name", "date"),
        ("itemprop", "datePublished"),
        ("name", "pubdate"),
        ("name", "article:published_time"),
    ]

    for attr, value in meta_props:
        tag = soup.find("meta", attrs={attr: value})
        if tag and (contenido := tag.get("content")):
            fecha_parseada = _parsear_fecha(contenido)
            if fecha_parseada:
                return fecha_parseada

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = script.get_text(strip=True)
            if not data:
                continue
            import json

            json_data = json.loads(data)
            if isinstance(json_data, list):
                for item in json_data:
                    fecha = item.get("datePublished") or item.get("dateCreated")
                    if fecha and (f := _parsear_fecha(fecha)):
                        return f
            elif isinstance(json_data, dict):
                fecha = json_data.get("datePublished") or json_data.get("dateCreated")
                if fecha and (f := _parsear_fecha(fecha)):
                    return f
        except Exception:
            continue

    # microdata en etiquetas <time>
    for time_tag in soup.find_all("time"):
        contenido = time_tag.get("datetime") or time_tag.get_text(strip=True)
        if contenido:
            fecha_parseada = _parsear_fecha(contenido)
            if fecha_parseada:
                return fecha_parseada

    return None


def _extraer_canonica_y_enlaces(soup: BeautifulSoup, url: str) -> Tuple[str, List[str]]:
    canonica = url
    link_canonico = soup.find("link", rel="canonical")
    if link_canonico and link_canonico.get("href"):
        canonica = link_canonico.get("href")

    enlaces: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if href and href.startswith("http"):
            enlaces.append(href)
    return canonica, enlaces


def extraer_texto_y_fecha_de_url(url: str, timeout: int = 10) -> Tuple[str, Optional[str], Optional[str], List[str]]:
    """Descarga una URL y devuelve texto, fecha y enlaces para crawling ligero."""

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if resp.status_code != 200:
            return "", None, None, []
        soup = BeautifulSoup(resp.text, "html.parser")
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        fecha_publicacion = extraer_fecha_publicacion(soup)
        canonica, enlaces = _extraer_canonica_y_enlaces(soup, url)
        return " ".join(parrafos), fecha_publicacion, canonica, enlaces
    except Exception:
        return "", None, None, []


def _buscar_ddg_iterativo(
    grupo_terminos: List[str],
    max_resultados: int,
    modo_coincidencia: str = "frase_exacta",
    dominio_filtro: Optional[str] = None,
    crawl_extendido: bool = False,
    profundidad_max: int = 3,
) -> List[ResultadoBusqueda]:
    """Busca usando ddgs de manera paginada y aplica crawling ligero opcional."""

    query = construir_query(grupo_terminos, modo_coincidencia)
    resultados: List[ResultadoBusqueda] = []
    vistos: set[str] = set()

    try:
        with DDGS() as buscador:
            for resultado in buscador.text(query, max_results=max_resultados, safesearch="moderate"):
                url = resultado.get("href") or resultado.get("url")
                if not url or url in vistos:
                    continue
                dominio = urlparse(url).netloc
                if dominio_filtro and dominio_filtro.lower() not in dominio.lower():
                    continue

                titulo = resultado.get("title") or ""
                snippet = resultado.get("body") or resultado.get("snippet") or ""
                texto, fecha_detectada, canonica, enlaces = extraer_texto_y_fecha_de_url(
                    url, timeout=settings.crawl_timeout
                )
                fecha_publicacion = fecha_detectada or resultado.get("date") or resultado.get("published")
                canonica_normalizada = canonica or url
                if canonica_normalizada in vistos:
                    continue
                vistos.add(canonica_normalizada)

                resultados.append(
                    ResultadoBusqueda(
                        url=url,
                        titulo=titulo,
                        dominio=dominio,
                        snippet=snippet,
                        texto=texto,
                        fecha_publicacion=fecha_publicacion,
                        canonica=canonica_normalizada,
                        fuente="ddg",
                        profundidad=1,
                    )
                )

                if crawl_extendido and len(resultados) < max_resultados:
                    secundarios = enlaces[: settings.crawl_profundo_max_enlaces]
                    for enlace in secundarios:
                        if len(resultados) >= max_resultados:
                            break
                        if enlace in vistos or (canonica and enlace == canonica):
                            continue
                        texto_s, fecha_s, canonica_s, _ = extraer_texto_y_fecha_de_url(
                            enlace, timeout=settings.crawl_timeout
                        )
                        vistos.add(canonica_s or enlace)
                        resultados.append(
                            ResultadoBusqueda(
                                url=enlace,
                                titulo=titulo,
                                dominio=urlparse(enlace).netloc,
                                snippet=snippet,
                                texto=texto_s,
                                fecha_publicacion=fecha_s,
                                canonica=canonica_s or enlace,
                                fuente="crawl",
                                profundidad=2,
                            )
                        )
                        if profundidad_max > 2 and texto_s:
                            # pequeños enlaces adicionales
                            try:
                                soup_tmp = BeautifulSoup(texto_s, "html.parser")
                            except Exception:
                                soup_tmp = None
                            if soup_tmp:
                                _, enlaces_tmp = _extraer_canonica_y_enlaces(soup_tmp, enlace)
                                for enlace2 in enlaces_tmp[:3]:
                                    if len(resultados) >= max_resultados:
                                        break
                                    if enlace2 in vistos:
                                        continue
                                    texto_t, fecha_t, canonica_t, _ = extraer_texto_y_fecha_de_url(
                                        enlace2, timeout=settings.crawl_timeout
                                    )
                                    vistos.add(canonica_t or enlace2)
                                    resultados.append(
                                        ResultadoBusqueda(
                                            url=enlace2,
                                            titulo=titulo,
                                            dominio=urlparse(enlace2).netloc,
                                            snippet=snippet,
                                            texto=texto_t,
                                            fecha_publicacion=fecha_t,
                                            canonica=canonica_t or enlace2,
                                            fuente="crawl",
                                            profundidad=3,
                                        )
                                    )
    except Exception as e:
        print(f"Error durante la búsqueda en DDG: {e}")
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
    profundidad: int,
    modo_coincidencia: str,
    dominio_filtro: Optional[str] = None,
    crawl_extendido: bool = False,
) -> List[ResultadoBusqueda]:
    """Selecciona la fuente principal y ejecuta la búsqueda."""

    max_resultados = PROFUNDIDAD_OPCIONES.get(
        min(max(profundidad, 1), settings.crawl_profundidad_maxima), PROFUNDIDAD_OPCIONES[3]
    )
    fuente = obtener_fuente_principal()
    if fuente == "ddg":
        return _buscar_ddg_iterativo(
            grupo_terminos,
            max_resultados,
            modo_coincidencia,
            dominio_filtro,
            crawl_extendido=crawl_extendido,
            profundidad_max=settings.crawl_profundidad_maxima,
        )
    return []
