"""Configuración de la aplicación y claves de API."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Valores de configuración cargados desde variables de entorno o `.env`.

    Los nombres siguen un esquema sencillo para que la app sea fácil de desplegar
    en diferentes entornos. Se utiliza SQLite por defecto para mantener la
    sencillez y permitir migrar a otros motores en el futuro.
    """

    database_url: str = Field(
        "sqlite:///menciones.db",
        description="Cadena de conexión de la base de datos",
        alias="DATABASE_URL",
    )
    brave_api_key: str | None = Field(
        default=None, description="Clave de Brave Search API", alias="BRAVE_API_KEY"
    )
    bing_api_key: str | None = Field(
        default=None, description="Clave de Bing Web Search", alias="BING_API_KEY"
    )
    serpapi_key: str | None = Field(
        default=None, description="Clave de SerpAPI", alias="SERPAPI_KEY"
    )

    # Configuración adicional de crawling y reportes
    crawl_timeout: int = Field(
        10, description="Tiempo máximo de espera para descargar una página en segundos"
    )
    crawl_profundo_max_enlaces: int = Field(
        20,
        description="Cantidad máxima de enlaces adicionales a seguir cuando el modo extendido está activo",
    )
    crawl_profundidad_maxima: int = Field(
        5, description="Profundidad máxima de exploración permitida"
    )
    reporte_titulo: str = Field(
        "Reporte de menciones", description="Título para los reportes generados"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        allow_mutation = False


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración de la aplicación cacheada."""

    return Settings(_env_file=Path(".env"))


settings = get_settings()
