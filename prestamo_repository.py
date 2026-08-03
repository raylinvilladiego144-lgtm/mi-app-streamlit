"""
prestamo_repository.py
Repositorio sincronizado exactamente con la estructura de modelos SQLAlchemy.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota, EstadoPrestamo, ModalidadInteres, EstadoCuota


class PrestamoRepository:
    """
    Repositorio optimizado para la gestión de préstamos y cuotas.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_prestamo(
        self,
        cliente_id,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "FIJO",
        fecha_inicio=None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Crea un nuevo préstamo y genera su cronograma de cuotas exacto.
        """
        if cliente_id is None:
            raise ValueError("Error: Debes seleccionar un cliente válido.")

        if hasattr(cliente_id, "id"):
            if cliente_id.id is None:
                raise ValueError("Error: El cliente seleccionado no tiene un ID válido.")
            c_id = int(cliente_id.id)
        else:
            try:
                c_id = int(cliente_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Error: Identificador de cliente inválido: {cliente_id}") from exc

        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()
        elif isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()

        cap_dec = Decimal(str(capital or 0.0))
        tasa_dec = Decimal(str(tasa_interes or 0.0)) / Decimal("100")
        cuotas_totales = int(num_cuotas or 1)

        monto_interes = cap_dec * tasa_dec
        monto_total = cap_dec + monto_interes
        valor_cuota = monto_total / Decimal(str(cuotas_totales)) if cuotas_totales > 0 else monto_total

        freq_upper = str(frecuencia or "FIJO").upper()
        if "DIARIO" in freq_upper or "DÍA" in freq_upper:
            delta_dias = 1
        elif "SEMANAL" in freq_upper:
            delta_dias = 7
        elif "QUINCENAL" in freq_upper:
            delta_dias = 15
        elif "MENSUAL" in freq_upper:
            delta_dias = 30
        else:
            delta_dias = 1

        fecha_vencimiento_final = fecha_inicio + timedelta(days=delta_dias * cuotas_totales)

        nuevo_prestamo = Prestamo(
            cliente_id=c_id,
            usuario=str(usuario or "admin"),
            capital=cap_dec,
            porcentaje_interes=Decimal(str(tasa_interes or 0.0)),
            monto_interes=monto_interes,
            monto_total=monto_total,
            numero_cuotas=cuotas_totales,
            modalidad=ModalidadInteres.FIJO,
            fecha_inicio=fecha_inicio,
            fecha_vencimiento=fecha_vencimiento_final,
            estado=EstadoPrestamo.ACTIVO,
            observaciones=str(observaciones or "")
        )

        self.db.add(nuevo_prestamo)
        self.db.flush()

        fecha_actual = fecha_inicio
        for i in range(1, cuotas_totales + 1):
            fecha_actual += timedelta(days=delta_dias)
            
            nueva_cuota = Cuota(
                prestamo_id=nuevo_prestamo.id,
                numero_cuota=i,
                monto_cuota=valor_cuota,
                monto_pagado=Decimal("0.00"),
                fecha_pago_esperada=fecha_actual,
                estado=EstadoCuota.PENDIENTE
            )
            self.db.add(nueva_cuota)

        self.db.commit()
        self.db.refresh(nuevo_prestamo)
        return nuevo_prestamo

    def listar_activos(self) -> list[Prestamo]:
        try:
            return self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO).all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_por_usuario(self, usuario: str) -> list[Prestamo]:
        try:
            return self.db.query(Prestamo).filter(Prestamo.usuario == usuario).all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_todos(self) -> list[Prestamo]:
        return self.db.query(Prestamo).all()
