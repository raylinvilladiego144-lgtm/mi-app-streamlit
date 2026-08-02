"""
app/database/base.py

Clase base declarativa para SQLAlchemy 2.0.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos SQLAlchemy.
    Todas las tablas del sistema heredarán de esta clase.
    """
    pass