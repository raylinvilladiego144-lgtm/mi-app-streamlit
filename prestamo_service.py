"""
prestamo_service.py
Servicio de lógica de negocio para la creación y gestión de préstamos.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo_repository import PrestamoRepository


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
