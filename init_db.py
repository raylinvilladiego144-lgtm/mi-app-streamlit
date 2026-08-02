"""
database/init_db.py

Inicializa la base de datos creando todas las tablas.
"""

from database.database import engine
from database.base import Base

# Importar todos los modelos para registrar las tablas
from models.cliente import Cliente
from models.prestamo import Prestamo, Cuota
from models.evento import EventoFinanciero


def init_db():
    """
    Crea todas las tablas si no existen.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()