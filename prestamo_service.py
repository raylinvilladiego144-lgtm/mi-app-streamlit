"""
app/services/prestamo_service.py

Servicio de dominio para la gestión de préstamos,
cronogramas, pagos y liquidaciones.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Tuple

from sqlalchemy.orm import Session

from app.models.prestamo import (
    Prestamo,
    Cuota,
    EstadoPrestamo,
    EstadoCuota,
    ModalidadInteres,
)

from app.models.evento import (
    EventoFinanciero,
    TipoEvento,
)

from app.repositories.prestamo_repository import (
    PrestamoRepository,
)


class PrestamoService:
    """
    Servicio encargado de la lógica de negocio de los préstamos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = PrestamoRepository(db)

    def crear_prestamo(
        self,
        cliente_id: int,
        capital: Decimal,
        porcentaje_interes: Decimal,
        numero_cuotas: int,
        fecha_inicio: date,
        frecuencia_dias: int = 1,
        observaciones: str | None = None,
    ) -> Prestamo:
        """
        Crea un préstamo y genera automáticamente
        el cronograma de cuotas.
        """

        monto_interes = (
            capital * porcentaje_interes
        ) / Decimal("100")

        monto_total = capital + monto_interes

        valor_cuota = (
            monto_total / Decimal(numero_cuotas)
        )

        fecha_vencimiento = (
            fecha_inicio
            + timedelta(
                days=numero_cuotas * frecuencia_dias
            )
        )

        prestamo = Prestamo(
            cliente_id=cliente_id,
            capital=capital,
            porcentaje_interes=porcentaje_interes,
            monto_interes=monto_interes,
            monto_total=monto_total,
            numero_cuotas=numero_cuotas,
            modalidad=ModalidadInteres.FIJO,
            fecha_inicio=fecha_inicio,
            fecha_vencimiento=fecha_vencimiento,
            estado=EstadoPrestamo.ACTIVO,
            observaciones=observaciones,
        )

        for numero in range(
            1,
            numero_cuotas + 1,
        ):

            cuota = Cuota(
                numero_cuota=numero,
                monto_cuota=valor_cuota,
                monto_pagado=Decimal("0.00"),
                fecha_pago_esperada=(
                    fecha_inicio
                    + timedelta(
                        days=numero * frecuencia_dias
                    )
                ),
                estado=EstadoCuota.PENDIENTE,
            )

            prestamo.cuotas.append(cuota)

        prestamo_creado = self.repo.crear_prestamo(
            prestamo
        )

        evento = EventoFinanciero(
            cliente_id=cliente_id,
            prestamo_id=prestamo_creado.id,
            tipo_evento=TipoEvento.PRESTAMO_CREADO,
            monto=capital,
            observacion=f"Desembolso préstamo #{prestamo_creado.id}",
        )

        self.repo.registrar_evento(evento)

        return prestamo_creado

    def registrar_pago_cuota(
        self,
        cuota_id: int,
        monto_abonado: Decimal,
        usuario: str = "admin",
    ) -> Tuple[Cuota, bool]:
        """
        Registra un pago sobre una cuota.

        Retorna:

        (cuota_actualizada, prestamo_liquidado)
        """

        cuota = (
            self.db.query(Cuota)
            .filter(Cuota.id == cuota_id)
            .first()
        )

        if cuota is None:
            raise ValueError(
                "La cuota no existe."
            )

        cuota.monto_pagado += monto_abonado

        if cuota.monto_pagado >= cuota.monto_cuota:

            cuota.estado = EstadoCuota.PAGADA
            cuota.fecha_pago_real = date.today()

        else:

            cuota.estado = EstadoCuota.PARCIAL

        evento = EventoFinanciero(
            cliente_id=cuota.prestamo.cliente_id,
            prestamo_id=cuota.prestamo_id,
            tipo_evento=TipoEvento.PAGO_RECIBIDO,
            monto=monto_abonado,
            usuario=usuario,
            observacion=(
                f"Abono cuota "
                f"{cuota.numero_cuota} "
                f"del préstamo "
                f"{cuota.prestamo_id}"
            ),
        )

        self.repo.registrar_evento(
            evento
        )

        cuotas_pendientes = [
            c
            for c in cuota.prestamo.cuotas
            if c.estado != EstadoCuota.PAGADA
        ]

        prestamo_liquidado = False

        if len(cuotas_pendientes) == 0:

            cuota.prestamo.estado = (
                EstadoPrestamo.LIQUIDADO
            )

            prestamo_liquidado = True

        self.db.commit()

        self.db.refresh(cuota)

        return (
            cuota,
            prestamo_liquidado,
        )