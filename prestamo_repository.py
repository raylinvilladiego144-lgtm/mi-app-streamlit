"""
prestamo_repository.py
Repositorio para la gestión y persistencia de préstamos y su cronograma de cuotas.
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
        cliente_id: int,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "Diario",
        fecha_inicio = None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Crea un nuevo préstamo, calcula los intereses totales, genera el cronograma 
        de cuotas de forma automática y lo guarda en la base de datos.
        """
        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()

        cap_dec = Decimal(str(capital))
        tasa_dec = Decimal(str(tasa_interes)) / Decimal("100")

        interes_total = cap_dec * tasa_dec
        monto_total = cap_dec + interes_total
        valor_cuota = monto_total / Decimal(str(num_cuotas))

        # Construcción dinámica para evitar errores de nombres de columnas en el modelo
        prestamo_data = {
            "cliente_id": cliente_id,
            "capital": cap_dec,
            "monto_total": monto_total,
            "num_cuotas": num_cuotas,
            "frecuencia": frecuencia,
            "observaciones": observaciones,
            "estado": EstadoPrestamo.ACTIVO,
            "fecha_creacion": datetime.utcnow()
        }

        # Asignar la tasa según los atributos reales que soporte el modelo Prestamo
        if hasattr(Prestamo, "tasa_interes"):
            prestamo_data["tasa_interes"] = float(tasa_interes)
        elif hasattr(Prestamo, "tasa"):
            prestamo_data["tasa"] = float(tasa_interes)
        elif hasattr(Prestamo, "interes"):
            prestamo_data["interes"] = float(tasa_interes)

        if hasattr(Prestamo, "usuario"):
            prestamo_data["usuario"] = usuario

        nuevo_prestamo = Prestamo(**prestamo_data)

        self.db.add(nuevo_prestamo)
        self.db.flush()

        frecuencia_lower = frecuencia.lower()
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

        fecha_actual = fecha_inicio
        if isinstance(fecha_actual, str):
            fecha_actual = datetime.strptime(fecha_actual, "%Y-%m-%d").date()

        for i in range(1, num_cuotas + 1):
            nueva_cuota = Cuota(
                prestamo_id=nuevo_prestamo.id,
                numero_cuota=i,
                monto_cuota=valor_cuota,
                monto_pagado=Decimal("0.00"),
                fecha_vencimiento=fecha_actual,
                estado=EstadoCuota.PENDIENTE
            )
            self.db.add(nueva_cuota)
            fecha_actual += timedelta(days=delta_dias)

        self.db.commit()
        self.db.refresh(nuevo_prestamo)

        return nuevo_prestamo

    def listar_activos(self) -> list[Prestamo]:
        """
        Retorna todos los préstamos activos para la administración de cartera.
        """
        return self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO).all()

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
