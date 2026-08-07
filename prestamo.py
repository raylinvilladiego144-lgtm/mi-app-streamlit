"""
app/models/prestamo.py

Modelos SQLAlchemy para la gestión de préstamos, cuotas,
estados y modalidades de interés.
"""
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from base import Base


class EstadoPrestamo(str, PyEnum):
    ACTIVO = "ACTIVO"
    LIQUIDADO = "LIQUIDADO"
    VENCIDO = "VENCIDO"
    ANULADO = "ANULADO"
    REFINANCIADO = "REFINANCIADO"


class EstadoCuota(str, PyEnum):
    PENDIENTE = "PENDIENTE"
    PARCIAL = "PARCIAL"
    PAGADA = "PAGADA"


class ModalidadInteres(str, PyEnum):
    FIJO = "FIJO"
    SOBRE_SALDO = "SOBRE_SALDO"


class Prestamo(Base):
    __tablename__ = "prestamos"

    id = Column(Integer, primary_key=True, index=True)
    
    # 🔑 Clave foránea referenciando a la tabla 'clientes'
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    
    # 🔒 CAMPO CLAVE PARA AISLAMIENTO POR USUARIO
    usuario = Column(String(50), default="admin", index=True, nullable=False)
    
    capital = Column(Numeric(12, 2), nullable=False)
    porcentaje_interes = Column(Numeric(5, 2), nullable=False)
    monto_interes = Column(Numeric(12, 2), nullable=False)
    monto_total = Column(Numeric(12, 2), nullable=False)
    
    numero_cuotas = Column(Integer, nullable=False)
    modalidad = Column(Enum(ModalidadInteres), default=ModalidadInteres.FIJO)
    
    fecha_inicio = Column(Date, nullable=False, default=date.today)
    fecha_vencimiento = Column(Date, nullable=False)
    
    estado = Column(Enum(EstadoPrestamo), default=EstadoPrestamo.ACTIVO)
    observaciones = Column(Text, nullable=True)

    # 🔗 RELACIÓN CON CLIENTE
    cliente = relationship("Cliente", back_populates="prestamos")

    # 🔗 RELACIÓN CON CUOTAS
    cuotas = relationship(
        "Cuota",
        back_populates="prestamo",
        cascade="all, delete-orphan"
    )


class Cuota(Base):
    __tablename__ = "cuotas"

    id = Column(Integer, primary_key=True, index=True)
    prestamo_id = Column(Integer, ForeignKey("prestamos.id"), nullable=False, index=True)
    
    numero_cuota = Column(Integer, nullable=False)
    monto_cuota = Column(Numeric(12, 2), nullable=False)
    monto_pagado = Column(Numeric(12, 2), default=Decimal("0.00"))
    
    fecha_pago_esperada = Column(Date, nullable=False)
    fecha_pago_real = Column(Date, nullable=True)
    
    estado = Column(Enum(EstadoCuota), default=EstadoCuota.PENDIENTE)

    prestamo = relationship("Prestamo", back_populates="cuotas")
