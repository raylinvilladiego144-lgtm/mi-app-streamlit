"""
caja_service.py
Servicio centralizado para la gestión financiera. 
Garantiza la integridad de la caja mediante eventos inmutables.
"""

from decimal import Decimal
from typing import Dict, List, Optional
try:
    import streamlit as st
except ImportError:
    st = None

from sqlalchemy.orm import Session
from evento import EventoFinanciero, TipoEvento
from prestamo import Prestamo, EstadoPrestamo, EstadoCuota

class CajaService:
    def __init__(self, db: Session, usuario_actual: str = "admin"):
        self.db = db
        self.usuario_actual = usuario_actual

    def _limpiar_cache(self):
        if st:
            st.cache_data.clear()

    def obtener_resumen_financiero(self) -> Dict[str, Decimal]:
        """Reconstruye el estado financiero basado exclusivamente en eventos."""
        eventos = self.db.query(EventoFinanciero).filter(
            EventoFinanciero.usuario == self.usuario_actual
        ).all()

        entradas = sum((e.monto for e in eventos if e.tipo_evento in 
                       [TipoEvento.PAGO_RECIBIDO, TipoEvento.APORTE_CAJA]), Decimal("0.00"))
        
        salidas = sum((e.monto for e in eventos if e.tipo_evento in 
                      [TipoEvento.PRESTAMO_CREADO, TipoEvento.RETIRO_CAJA]), Decimal("0.00"))

        caja_disponible = entradas - salidas

        # Cálculo de cartera (capital prestado pendiente)
        prestamos = self.db.query(Prestamo).filter(
            Prestamo.usuario == self.usuario_actual,
            Prestamo.estado == EstadoPrestamo.ACTIVO
        ).all()

        capital_prestado = Decimal("0.00")
        for p in prestamos:
            saldo_cuotas = sum((c.monto_cuota - (c.monto_pagado or 0) for c in p.cuotas 
                              if c.estado != EstadoCuota.PAGADA), Decimal("0.00"))
            capital_prestado += saldo_cuotas if saldo_cuotas > 0 else (p.capital or 0)

        return {
            "caja_disponible": caja_disponible,
            "capital_prestado": capital_prestado,
            "capital_total": caja_disponible + capital_prestado,
            "entradas_totales": entradas,
            "salidas_totales": salidas
        }

    def registrar_ingreso(self, monto: Decimal, observacion: str, tipo: TipoEvento = TipoEvento.APORTE_CAJA) -> EventoFinanciero:
        """Método genérico para registrar entradas de dinero a la caja."""
        monto = Decimal(str(monto))
        evento = EventoFinanciero(
            tipo_evento=tipo,
            monto=monto,
            usuario=self.usuario_actual,
            observacion=observacion
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        self._limpiar_cache()
        return evento

    def registrar_pago_cuota(self, monto: Decimal, observacion: str) -> EventoFinanciero:
        """Registra específicamente un abono o pago recibido de una cuota de préstamo."""
        return self.registrar_ingreso(monto, observacion, tipo=TipoEvento.PAGO_RECIBIDO)

    # Aliases para compatibilidad
    registrar_aporte = registrar_ingreso

    def registrar_retiro(self, monto: Decimal, observacion: str) -> EventoFinanciero:
        """Registra un retiro validando saldo disponible."""
        monto = Decimal(str(monto))
        resumen = self.obtener_resumen_financiero()
        
        if monto > resumen["caja_disponible"]:
            raise ValueError("Saldo insuficiente en caja.")

        evento = EventoFinanciero(
            tipo_evento=TipoEvento.RETIRO_CAJA,
            monto=monto,
            usuario=self.usuario_actual,
            observacion=observacion
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        self._limpiar_cache()
        return evento

    def listar_movimientos(self, limite: int = 100) -> List[EventoFinanciero]:
        return self.db.query(EventoFinanciero).filter(
            EventoFinanciero.usuario == self.usuario_actual
        ).order_by(EventoFinanciero.id.desc()).limit(limite).all()
