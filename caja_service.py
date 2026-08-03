"""
app/services/caja_service.py

Servicio encargado de calcular el estado financiero de la caja,
capital disponible, saldo pendiente por cobrar en préstamos y
registrar/consultar movimientos de aporte, retiro y eventos del sistema
filtrados por el usuario actual.
"""

from decimal import Decimal
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.evento import (
    EventoFinanciero,
    TipoEvento,
)
from app.models.prestamo import (
    Prestamo,
    EstadoPrestamo,
    EstadoCuota,
)


class CajaService:
    """
    Servicio para administrar la caja del sistema por usuario.
    """

    def __init__(self, db: Session, usuario_actual: str = "admin"):
        self.db = db
        self.usuario_actual = usuario_actual

    def obtener_saldo_actual(self) -> Decimal:
        """
        Retorna el saldo disponible en caja del usuario actual.
        """
        resumen = self.obtener_resumen_financiero()
        return resumen["caja_disponible"]

    obtener_saldo = obtener_saldo_actual

    def listar_movimientos(self, limite: int = 100) -> List[EventoFinanciero]:
        """
        Obtiene la lista de movimientos y eventos financieros del usuario actual.
        """
        query = self.db.query(EventoFinanciero)
        if hasattr(EventoFinanciero, "usuario"):
            query = query.filter(EventoFinanciero.usuario == self.usuario_actual)

        return (
            query.order_by(
                EventoFinanciero.fecha.desc()
                if hasattr(EventoFinanciero, "fecha")
                else EventoFinanciero.id.desc()
            )
            .limit(limite)
            .all()
        )

    obtener_historial = listar_movimientos

    def obtener_resumen_financiero(self) -> Dict[str, Decimal]:
        """
        Reconstruye el estado financiero leyendo únicamente el historial del usuario actual.
        """
        query_eventos = self.db.query(EventoFinanciero)
        if hasattr(EventoFinanciero, "usuario"):
            query_eventos = query_eventos.filter(EventoFinanciero.usuario == self.usuario_actual)

        eventos = query_eventos.all()

        entradas_caja = Decimal("0.00")
        salidas_caja = Decimal("0.00")

        for evento in eventos:
            if evento.tipo_evento in (
                TipoEvento.PAGO_RECIBIDO,
                TipoEvento.APORTE_CAJA,
            ):
                entradas_caja += evento.monto

            elif evento.tipo_evento in (
                TipoEvento.PRESTAMO_CREADO,
                TipoEvento.RETIRO_CAJA,
            ):
                salidas_caja += evento.monto

        caja_disponible = entradas_caja - salidas_caja

        # Filtrar préstamos activos del usuario
        query_prestamos = self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO)
        if hasattr(Prestamo, "usuario"):
            query_prestamos = query_prestamos.filter(Prestamo.usuario == self.usuario_actual)

        prestamos_activos = query_prestamos.all()

        capital_prestado = Decimal("0.00")

        for prestamo in prestamos_activos:
            if hasattr(prestamo, "cuotas") and prestamo.cuotas:
                for cuota in prestamo.cuotas:
                    if cuota.estado != EstadoCuota.PAGADA:
                        monto_pagado = cuota.monto_pagado or Decimal("0.00")
                        saldo_cuota = cuota.monto_cuota - monto_pagado
                        if saldo_cuota > Decimal("0.00"):
                            capital_prestado += saldo_cuota
            else:
                capital_prestado += prestamo.capital

        capital_total = caja_disponible + capital_prestado

        return {
            "caja_disponible": caja_disponible,
            "capital_prestado": capital_prestado,
            "capital_total": capital_total,
            "entradas_totales": entradas_caja,
            "salidas_totales": salidas_caja,
        }

    def registrar_aporte(
        self,
        monto: Decimal,
        observacion: str,
    ) -> EventoFinanciero:
        """
        Registra un aporte asignado al usuario actual.
        """
        evento = EventoFinanciero(
            tipo_evento=TipoEvento.APORTE_CAJA,
            monto=monto,
            usuario=self.usuario_actual,
            observacion=observacion,
        )

        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)

        return evento

    def registrar_retiro(
        self,
        monto: Decimal,
        observacion: str,
    ) -> EventoFinanciero:
        """
        Registra un retiro del usuario validando disponibilidad.
        """
        resumen = self.obtener_resumen_financiero()

        if monto > resumen["caja_disponible"]:
            raise ValueError(
                "No hay suficiente dinero disponible en caja para realizar este retiro."
            )

        evento = EventoFinanciero(
            tipo_evento=TipoEvento.RETIRO_CAJA,
            monto=monto,
            usuario=self.usuario_actual,
            observacion=observacion,
        )

        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)

        return evento