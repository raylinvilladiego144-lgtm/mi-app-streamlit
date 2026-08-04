"""
database.py
Configuración de la sesión de base de datos SQLAlchemy para la nube.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Intenta buscar la URL en los secretos de Streamlit Cloud, o usa una local por defecto si estás en tu PC
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///prestamos_v2.db")

# Ajuste automático del motor según si es SQLite o PostgreSQL (Cloud)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Si usas PostgreSQL en la nube (Supabase / Neon)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

def init_db():
    # Importa la Base desde donde la tengas definida
    from base import Base
    Base.metadata.create_all(bind=engine)
