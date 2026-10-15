"""
database.py
Módulo de conexión y gestión de base de datos blindado para producción.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuración robusta: por defecto usa SQLite local persistente en el contenedor
database_url = os.environ.get("DATABASE_URL")

if not database_url or database_url.strip() == "":
    DATABASE_URL = "sqlite:///prestamos_v2.db"
else:
    DATABASE_URL = database_url

# Inicialización del motor según el tipo de base de datos.
#
# IMPORTANTE: create_engine() puede fallar al momento de crearse (no solo al
# conectar) cuando falta el driver correspondiente instalado (por ejemplo
# 'psycopg' para postgresql+psycopg://...). Ese fallo ocurre ANTES de que
# exista cualquier conexión, así que lo capturamos aquí mismo: si pasa,
# dejamos 'engine' en None y guardamos el motivo en ENGINE_INIT_ERROR, en vez
# de dejar que la excepción (ModuleNotFoundError, que ES un ImportError)
# reviente sin control la importación de este módulo — eso es justo lo que
# producía la pantalla "ImportError... redacted" en Streamlit Cloud.
ENGINE_INIT_ERROR: str | None = None
engine = None

try:
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
except Exception as e:
    ENGINE_INIT_ERROR = f"{type(e).__name__}: {e}"

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


def verificar_conexion() -> tuple[bool, str]:
    """
    Intenta abrir una conexión real contra DATABASE_URL y devuelve
    (True, "") si funciona, o (False, mensaje_completo_del_error) si falla.

    Streamlit Cloud REDACTA el texto de cualquier excepción que llegue sin
    capturar hasta la pantalla de error ("This app has encountered an
    error..."), así que la única forma de ver el motivo real (credenciales,
    host, SSL, base de datos pausada, etc.) es atraparlo nosotros mismos
    aquí y mostrarlo con st.error() en vez de dejar que la excepción reviente
    sin control.
    """
    if engine is None:
        # El motor nunca llegó a crearse (por ejemplo, falta el driver
        # 'psycopg' instalado). No hay nada contra qué conectar todavía.
        return False, ENGINE_INIT_ERROR or "El motor de base de datos no se pudo inicializar (motivo desconocido)."

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def init_db():
    """Crea las tablas de forma segura al arrancar la aplicación y asegura permisos."""
    if engine is None:
        # Sin motor no hay nada que inicializar; verificar_conexion() ya
        # habrá mostrado el motivo real en main.py antes de llegar aquí.
        return
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
