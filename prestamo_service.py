"""
prestamo_service.py
Servicio de lógica de negocio para la creación y gestión de préstamos.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import streamlit as st  # ⚡ Importado para refrescar la interfaz de forma instantánea
from prestamo_repository import PrestamoRepository
from prestamo import EstadoCuota, EstadoPrestamo
from evento import EventoFinanciero, TipoEvento


class PrestamoService:
    """
    Servicio encargado de coordinar las reglas de negocio de los préstamos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = PrestamoRepository(db)

    def crear_prestamo(
        self,
        cliente_id,
        capital: float | Decimal,
        porcentaje_interes: float | Decimal,
        numero_cuotas: int,
        fecha_inicio=None,
        frecuencia_dias: int = 7,
        observaciones: str = "",
        usuario: str = "admin",
    ):
        if cliente_id is None:
            raise ValueError("Debe seleccionar un cliente válido.")
        
        c_id = int(cliente_id.id) if hasattr(cliente_id, "id") else int(cliente_id)

        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()
        elif isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()

        cap_dec = Decimal(str(capital or 0.0))
        num_cuotas_int = int(numero_cuotas or 1)
        delta_dias = int(frecuencia_dias or 7)

        nuevo_prestamo = self.repo.crear_prestamo(
            cliente_id=c_id,
            capital=cap_dec,
            tasa_interes=porcentaje_interes,
            num_cuotas=num_cuotas_int,
            frecuencia="FIJO",
            fecha_inicio=fecha_inicio,
            observaciones=observaciones,
            usuario=usuario
        )

        return nuevo_prestamo

    def registrar_pago_inteligente(
        self,
        prestamo_id: int,
        monto_pagado: float | Decimal,
        usuario_actual: str = "admin",
        observacion: str = ""
    ) -> EventoFinanciero:
        """
        Registra un pago de forma inteligente: distribuye el dinero ingresado 
        cubriendo la cuota actual y abonando automáticamente a las siguientes si sobra.
        """
        prestamo = self.repo.obtener_por_id(prestamo_id) if hasattr(self.repo, "obtener_por_id") else self.db.query(self.repo.model).filter_by(id=prestamo_id).first()
        
        if not prestamo:
            raise ValueError("El préstamo seleccionado no existe.")

        monto_restante = Decimal(str(monto_pagado or 0.0))
        
        # Obtener cuotas pendientes ordenadas secuencialmente
        cuotas_pendientes = [
            c for c in prestamo.cuotas 
            if c.estado != EstadoCuota.PAGADA
        ]
        cuotas_pendientes.sort(key=lambda x: x.numero_cuota if hasattr(x, 'numero_cuota') else x.id)

        total_abonado_efectivo = Decimal("0.00")

        for cuota in cuotas_pendientes:
            if monto_restante <= Decimal("0.00"):
                break

            monto_ya_pagado = cuota.monto_pagado or Decimal("0.00")
            saldo_pendiente_cuota = cuota.monto_cuota - monto_ya_pagado

            if monto_restante >= saldo_pendiente_cuota:
                # El dinero cubre esta cuota por completo
                monto_restante -= saldo_pendiente_cuota
                cuota.monto_pagado = cuota.monto_cuota
                cuota.estado = EstadoCuota.PAGADA
                total_abonado_efectivo += saldo_pendiente_cuota
            else:
                # El dinero cubre una parte (abono parcial a la cuota)
                cuota.monto_pagado = monto_ya_pagado + monto_restante
                cuota.estado = EstadoCuota.PARCIAL if hasattr(EstadoCuota, 'PARCIAL') else EstadoCuota.ACTIVA
                total_abonado_efectivo += monto_restante
                monto_restante = Decimal("0.00")

        # Si sobra dinero tras liquidar todas las cuotas pendientes
        if monto_restante > Decimal("0.00"):
            total_abonado_efectivo += monto_restante

        # Registrar el evento financiero en la caja del usuario
        evento = EventoFinanciero(
            tipo_evento=TipoEvento.PAGO_RECIBIDO,
            monto=total_abonado_efectivo,
            usuario=usuario_actual,
            observacion=f"Pago inteligente distribuido en cuotas. {observacion}"
        )

        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)

        # ⚡ Limpieza inmediata de la caché de Streamlit para actualizar los saldos al instante
        st.cache_data.clear()

        return evento
