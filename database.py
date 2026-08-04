"""
database.py
Configuración de la sesión de base de datos SQLAlchemy para Supabase.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Obtiene la URL de los secretos de Streamlit Cloud
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///prestamos_v2.db")

# Configuración del motor de base de datos
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Conexión limpia y directa compatible con Supabase
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    """Crea las tablas automáticamente en Supabase si no existen."""
    from base import Base
    Base.metadata.create_all(bind=engine)
