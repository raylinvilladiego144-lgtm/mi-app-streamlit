"""
app/models/evento.py
Modelo ORM para Eventos Financieros e Historial de Caja.
"""

from datetime import datetime
from typing import Optional
from decimal import Decimal
import enum

from sqlalchemy import String, Text, DateTime, Numeric, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from base import Base


class TipoEvento(str, enum.Enum):
    PRESTAMO_CREADO = "PRESTAMO_CREADO"
    PAGO_RECIBIDO = "PAGO_RECIBIDO"
    REPOSICION_REALIZADA = "REPOSICION_REALIZADA"
    RENOVACION_REALIZADA = "RENOVACION_REALIZADA"
    LIQUIDACION_PRESTAMO = "LIQUIDACION_PRESTAMO"
    APORTE_CAJA = "APORTE_CAJA"
    RETIRO_CAJA = "RETIRO_CAJA"
    CLIENTE_BLOQUEADO = "CLIENTE_BLOQUEADO"


class EventoFinanciero(Base):
    __tablename__ = "eventos_financieros"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"), nullable=True, index=True)
    prestamo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("prestamos.id"), nullable=True, index=True)

    tipo_evento: Mapped[TipoEvento] = mapped_column(SQLEnum(TipoEvento), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    usuario: Mapped[str] = mapped_column(String(50), default="admin", nullable=False)
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
