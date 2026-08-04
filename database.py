"""
database.py
Módulo de conexión y gestión de base de datos blindado para producción.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuración robusta: por defecto usa SQLite local persistente en el contenedor
database_url = os.environ.get("DATABASE_URL")

if not database_url or database_url.strip() == "":
    DATABASE_URL = "sqlite:///prestamos_v2.db"
else:
    DATABASE_URL = database_url

# Inicialización del motor según el tipo de base de datos
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    """Crea las tablas de forma segura al arrancar la aplicación."""
    try:
        from base import Base
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Aviso en la inicialización de la base de datos: {e}")
