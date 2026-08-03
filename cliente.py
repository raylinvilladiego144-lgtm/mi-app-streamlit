"""
cliente.py
Modelo ORM para la entidad Cliente.
"""

from datetime import datetime
from typing import Optional, List
import enum
from sqlalchemy import String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from base import Base


class EstadoCliente(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    BLOQUEADO = "BLOQUEADO"


class CalificacionCliente(str, enum.Enum):
    EXCELENTE = "EXCELENTE"
    BUENO = "BUENO"
    REGULAR = "REGULAR"
    RIESGOSO = "RIESGOSO"
    BLOQUEADO = "BLOQUEADO"


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    documento: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    telefono: Mapped[str] = mapped_column(String(30), nullable=False)
    direccion: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    usuario: Mapped[str] = mapped_column(String(50), default="admin", index=True, nullable=False)

    estado: Mapped[EstadoCliente] = mapped_column(
        SQLEnum(EstadoCliente), default=EstadoCliente.ACTIVO, nullable=False
    )
    calificacion: Mapped[CalificacionCliente] = mapped_column(
        SQLEnum(CalificacionCliente), default=CalificacionCliente.BUENO, nullable=False
    )
    
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    prestamos: Mapped[List["Prestamo"]] = relationship("Prestamo", back_populates="cliente")
