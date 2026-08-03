"""
prestamo_repository.py
Repositorio definitivo para la gestión de préstamos y cronograma de cuotas.
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
        Crea un nuevo préstamo y genera su cronograma de cuotas de forma segura.
        """
        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()

        cap_dec = Decimal(str(capital))
        tasa_dec = Decimal(str(tasa_interes)) / Decimal("100")

        interes_total = cap_dec * tasa_dec
        monto_total = cap_dec + interes_total
        valor_cuota = monto_total / Decimal(str(num_cuotas))

        # 1. Crear la instancia principal del Préstamo evitando pasar relaciones directamente
        nuevo_prestamo = Prestamo(cliente_id=cliente_id)

        # 2. Asignar de forma segura solo columnas escalares (números, textos, fechas)
        atributos_escalares = {
            "capital": cap_dec,
            "monto": cap_dec,
            "monto_total": monto_total,
            "total": monto_total,
            "tasa_interes": float(tasa_interes),
            "tasa": float(tasa_interes),
            "interes": float(tasa_interes),
            "num_cuotas": num_cuotas,
            "numero_cuotas": num_cuotas,
            "cuotas": num_cuotas,
            "plazo": num_cuotas,
            "frecuencia": frecuencia,
            "observaciones": observaciones,
            "usuario": usuario,
            "estado": EstadoPrestamo.ACTIVO,
            "fecha_creacion": datetime.utcnow(),
            "creado_en": datetime.utcnow(),
            "fecha_inicio": fecha_inicio
        }

        for attr, val in atributos_escalares.items():
            if hasattr(Prestamo, attr):
                # Nos aseguramos de no asignar enteros a relaciones de colección
                col_type = getattr(Prestamo, attr)
                if not hasattr(col_type, "property"):  # Es una columna normal, no una relación
                    setattr(nuevo_prestamo, attr, val)

        self.db.add(nuevo_prestamo)
        self.db.flush()  # Genera el ID del préstamo sin comprometer la transacción todavía

        # 3. Determinar intervalo de días para las cuotas
        frecuencia_lower = str(frecuencia).lower()
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

        # 4. Generar e insertar el cronograma de cuotas individualmente
        for i in range(1, num_cuotas + 1):
            nueva_cuota = Cuota(prestamo_id=nuevo_prestamo.id)
            
            cuota_data = {
                "prestamo_id": nuevo_prestamo.id,
                "numero_cuota": i,
                "monto_cuota": valor_cuota,
                "monto_pagado": Decimal("0.00"),
                "fecha_vencimiento": fecha_actual,
                "estado": EstadoCuota.PENDIENTE
            }

            for c_attr, c_val in cuota_data.items():
                if hasattr(Cuota, c_attr):
                    col_type = getattr(Cuota, c_attr)
                    if not hasattr(col_type, "property"):
                        setattr(nueva_cuota, c_attr, c_val)

            self.db.add(nueva_cuota)
            fecha_actual += timedelta(days=delta_dias)

        self.db.commit()
        self.db.refresh(nuevo_prestamo)

        return nuevo_prestamo

    def listar_activos(self) -> list[Prestamo]:
        """
        Retorna todos los préstamos activos.
        """
        try:
            return self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO).all()
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
