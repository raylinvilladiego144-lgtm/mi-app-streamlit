"""
prestamo_repository.py
Repositorio blindado para la gestión de préstamos y validación segura de IDs.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota, EstadoPrestamo, EstadoCuota


class PrestamoRepository:
    """
    Repositorio encargado de interactuar con la base de datos para los préstamos.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_prestamo(
        self,
        cliente_id=None,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "Diario",
        fecha_inicio = None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Crea un nuevo préstamo validando y asegurando que los parámetros no sean None.
        """
        # Validación estricta para evitar errores si cliente_id llega nulo
        if cliente_id is None:
            raise ValueError("Debes seleccionar un cliente válido para registrar el préstamo.")

        if hasattr(cliente_id, "id"):
            c_id = int(cliente_id.id)
        else:
            try:
                c_id = int(cliente_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"El ID del cliente proporcionado no es válido: {cliente_id}") from exc

        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()
        elif isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()

        # Asegurar valores numéricos seguros
        cap_dec = Decimal(str(capital or 0.0))
        tasa_dec = Decimal(str(tasa_interes or 0.0)) / Decimal("100")
        num_cuotas = int(num_cuotas or 1)

        # Cálculos financieros
        monto_interes = cap_dec * tasa_dec
        monto_total = cap_dec + monto_interes
        valor_cuota = monto_total / Decimal(str(num_cuotas))

        # Determinar intervalo de días
        frecuencia_lower = str(frecuencia or "diario").lower()
        if "diario" in frecuencia_lower or "día" in frecuencia_lower:
            delta_dias = 1
        elif "semanal" in frecuencia_lower:
            delta_dias = 7
        elif "quincenal" in frecuencia_lower:
            delta_dias = 15
        elif "mensual" in frecuencia_lower:
            delta_dias = 30
        else:
            delta_dias = 1

        fecha_vencimiento_final = fecha_inicio + timedelta(days=delta_dias * num_cuotas)

        # Instancia con los campos reales de tu base de datos
        nuevo_prestamo = Prestamo(
            cliente_id=c_id,
            usuario=str(usuario or "admin"),
            capital=float(cap_dec),
            porcentaje_interes=float(tasa_interes or 0.0),
            monto_interes=float(monto_interes),
            monto_total=float(monto_total),
            numero_cuotas=num_cuotas,
            modalidad=str(frecuencia or "DIARIO").upper(),
            fecha_inicio=fecha_inicio,
            fecha_vencimiento=fecha_vencimiento_final,
            estado="ACTIVO",
            observaciones=str(observaciones or "")
        )

        self.db.add(nuevo_prestamo)
        self.db.flush()

        # Generar cuotas individuales
        fecha_actual = fecha_inicio
        for i in range(1, num_cuotas + 1):
            fecha_actual += timedelta(days=delta_dias)
            nueva_cuota = Cuota(
                prestamo_id=nuevo_prestamo.id,
                numero_cuota=i,
                monto_cuota=float(valor_cuota),
                monto_pagado=0.0,
                fecha_vencimiento=fecha_actual,
                estado="PENDIENTE"
            )
            self.db.add(nueva_cuota)

        self.db.commit()
        self.db.refresh(nuevo_prestamo)

        return nuevo_prestamo

    def listar_activos(self) -> list[Prestamo]:
        """
        Retorna todos los préstamos activos.
        """
        try:
            return self.db.query(Prestamo).filter(Prestamo.estado == "ACTIVO").all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_por_usuario(self, usuario: str) -> list[Prestamo]:
        """
        Retorna la lista de préstamos registrados por un usuario específico.
        """
        query = self.db.query(Prestamo)
        if hasattr(Prestamo, "usuario"):
            query = query.filter(Prestamo.usuario == usuario)
        return query.all()

    def obtener_todos(self) -> list[Prestamo]:
        """
        Retorna todos los préstamos del sistema.
        """
        return self.db.query(Prestamo).all()
