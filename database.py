"""
database.py
Configuración de la sesión de base de datos SQLAlchemy para Supabase con SSL forzado.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///prestamos_v2.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Forzamos el modo SSL requerido por Supabase directamente en los argumentos de conexión
    engine = create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True,
        pool_recycle=3600,
    )

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    """Crea las tablas automáticamente en Supabase si no existen."""
    from base import Base
    Base.metadata.create_all(bind=engine)
