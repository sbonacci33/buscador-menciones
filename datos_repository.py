"""Capa de acceso a datos basada en SQLite y SQLAlchemy.

Centraliza la creación de tablas y funciones de escritura/lectura para que la
lógica de negocio pueda permanecer limpia. Las tablas están pensadas para ser
migradas fácilmente a otros motores (PostgreSQL, MySQL) si el producto crece.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
    text as sql_text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

from config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Pagina(Base):
    __tablename__ = "paginas"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    dominio = Column(String, index=True)
    titulo = Column(String)
    texto = Column(Text)
    fecha_publicacion = Column(DateTime, nullable=True)
    fecha_primera_vez_vista = Column(DateTime, default=datetime.utcnow)
    fecha_ultima_vez_vista = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    menciones = relationship("Mencion", back_populates="pagina", cascade="all, delete-orphan")


class Termino(Base):
    __tablename__ = "terminos"

    id = Column(Integer, primary_key=True)
    termino_texto = Column(String, unique=True, nullable=False)

    menciones = relationship("Mencion", back_populates="termino", cascade="all, delete-orphan")


class Mencion(Base):
    __tablename__ = "menciones"
    __table_args__ = (UniqueConstraint("pagina_id", "termino_id", name="uix_pagina_termino"),)

    id = Column(Integer, primary_key=True)
    pagina_id = Column(Integer, ForeignKey("paginas.id"), nullable=False)
    termino_id = Column(Integer, ForeignKey("terminos.id"), nullable=False)
    cantidad_menciones = Column(Integer, default=0)

    pagina = relationship("Pagina", back_populates="menciones")
    termino = relationship("Termino", back_populates="menciones")


@contextmanager
def session_scope() -> Iterable[Session]:
    """Context manager para manejar sesiones y commits de forma segura."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema() -> None:
    """Asegura que las tablas y columnas necesarias existan."""

    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    columnas_paginas = {col["name"] for col in inspector.get_columns("paginas")}
    if "fecha_publicacion" not in columnas_paginas:
        with engine.connect() as conn:
            conn.execute(
                sql_text("ALTER TABLE paginas ADD COLUMN fecha_publicacion DATETIME")
            )
            conn.commit()


def inicializar_bd() -> None:
    """Crea las tablas en la base de datos si no existen y aplica migraciones simples."""

    ensure_schema()


def _obtener_o_crear_termino(session: Session, termino_texto: str) -> Termino:
    termino = session.execute(
        select(Termino).where(Termino.termino_texto == termino_texto)
    ).scalar_one_or_none()
    if termino is None:
        termino = Termino(termino_texto=termino_texto)
        session.add(termino)
        session.flush()
    return termino


def guardar_pagina(url: str, titulo: str, texto: str, fecha_publicacion: datetime | None) -> int:
    """Inserta o actualiza una página y devuelve su ID."""

    dominio = urlparse(url).netloc
    with session_scope() as session:
        pagina = session.execute(select(Pagina).where(Pagina.url == url)).scalar_one_or_none()
        ahora = datetime.utcnow()
        if pagina:
            pagina.titulo = pagina.titulo or titulo
            pagina.texto = pagina.texto or texto
            pagina.dominio = pagina.dominio or dominio
            pagina.fecha_publicacion = pagina.fecha_publicacion or fecha_publicacion
            pagina.fecha_ultima_vez_vista = ahora
        else:
            pagina = Pagina(
                url=url,
                dominio=dominio,
                titulo=titulo,
                texto=texto,
                fecha_publicacion=fecha_publicacion,
                fecha_primera_vez_vista=ahora,
                fecha_ultima_vez_vista=ahora,
            )
            session.add(pagina)
            session.flush()
        return int(pagina.id)


def registrar_menciones(pagina_id: int, menciones_por_termino: Dict[str, int]) -> None:
    """Registra las menciones de cada término para una página concreta."""

    with session_scope() as session:
        pagina = session.get(Pagina, pagina_id)
        if not pagina:
            return

        for termino_texto, cantidad in menciones_por_termino.items():
            if cantidad <= 0:
                continue
            termino = _obtener_o_crear_termino(session, termino_texto)
            mencion = session.execute(
                select(Mencion).where(
                    Mencion.pagina_id == pagina.id, Mencion.termino_id == termino.id
                )
            ).scalar_one_or_none()
            if mencion:
                mencion.cantidad_menciones = cantidad
            else:
                session.add(
                    Mencion(
                        pagina_id=pagina.id,
                        termino_id=termino.id,
                        cantidad_menciones=cantidad,
                    )
                )


def obtener_paginas_con_menciones(
    terminos: List[str],
    dominio_filtro: Optional[str] = None,
    limite: int | None = None,
) -> pd.DataFrame:
    """Devuelve un DataFrame con páginas y menciones para los términos indicados."""

    with session_scope() as session:
        query = session.query(Pagina).join(Mencion).join(Termino)
        if terminos:
            query = query.filter(Termino.termino_texto.in_(terminos))
        if dominio_filtro:
            query = query.filter(Pagina.dominio.ilike(f"%{dominio_filtro}%"))

        paginas = query.all()

        registros: List[Dict[str, object]] = []
        for pagina in paginas:
            menciones_map = {m.termino.termino_texto: m.cantidad_menciones for m in pagina.menciones}
            registro = {
                "url": pagina.url,
                "titulo": pagina.titulo or "",
                "dominio": pagina.dominio,
                "texto": pagina.texto or "",
                "fecha_publicacion": pagina.fecha_publicacion,
                "fecha_primera_vez_vista": pagina.fecha_primera_vez_vista,
                "fecha_ultima_vez_vista": pagina.fecha_ultima_vez_vista,
                "menciones_por_termino": menciones_map,
                "menciones_totales_pagina": sum(menciones_map.values()),
            }
            registros.append(registro)

        df = pd.DataFrame(registros)
        if limite:
            df = df.head(limite)
        return df
