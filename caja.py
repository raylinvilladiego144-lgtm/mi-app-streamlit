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

def asegurar_permisos_sqlite(db_path="prestamos_v2.db"):
    """Asegura que el archivo SQLite local tenga permisos de lectura y escritura."""
    if os.path.exists(db_path):
        try:
            os.chmod(db_path, 0o666)
        except Exception as e:
            print(f"No se pudieron ajustar los permisos del archivo SQLite: {e}")

def init_db():
    """Crea las tablas de forma segura al arrancar la aplicación y asegura permisos."""
    try:
        from base import Base
        Base.metadata.create_all(bind=engine)
        
        # Si se usa SQLite, se asegura de que el archivo no quede en modo solo lectura
        if DATABASE_URL.startswith("sqlite"):
            # Extraer nombre del archivo si viene en formato sqlite:///nombre.db
            path_archivo = DATABASE_URL.replace("sqlite:///", "").split("?")[0]
            if path_archivo:
                asegurar_permisos_sqlite(path_archivo)
                
    except Exception as e:
        print(f"Aviso en la inicialización de la base de datos: {e}")
