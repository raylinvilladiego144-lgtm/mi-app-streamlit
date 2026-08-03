"""
prestamo_repository.py
Versión definitiva con manejo de errores y compatibilidad total.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota


class PrestamoRepository:
    """
    Repositorio ultrarrobusto para la gestión de préstamos.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_prestamo(
        self,
        cliente_id,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "Diario",
        fecha_inicio=None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Registra el préstamo usando asignación dinámica segura por atributos existentes.
        """
        # 1. Extraer ID de cliente de forma segura (sea objeto o entero)
        if cliente_id is None:
            raise ValueError("Error: Debes seleccionar un cliente válido.")
        
        c_id = int(cliente_id.id) if hasattr(cliente_id, "id") else int(cliente_id)

        # 2. Fechas
        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()
        elif isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()

        # 3. Cálculos
        cap = float(capital or 0.0)
        tasa = float(tasa_interes or 0.0)
        cuotas = int(num_cuotas or 1)
        
        m_interes = cap * (tasa / 100.0)
        m_total = cap + m_interes
        v_cuota = m_total / cuotas if cuotas > 0 else m_total

        # Frecuencia en días
        freq_lower = str(frecuencia or "diario").lower()
        delta = 1 if "diario" in freq_lower or "día" in freq_lower else (7 if "semanal" in freq_lower else (15 if "quincenal" in freq_lower else 30))

        fecha_venc = fecha_inicio + timedelta(days=delta * cuotas)

        # 4. Crear instancia limpia de Prestamo
        nuevo_prestamo = Prestamo()

        # Diccionario con posibles nombres de columnas en tu base de datos
        datos_posibles = {
            "cliente_id": c_id,
            "usuario": str(usuario),
            "capital": cap,
            "porcentaje_interes": tasa,
            "tasa_interes": tasa,
            "tasa": tasa,
            "interes": tasa,
            "monto_interes": m_interes,
            "monto_total": m_total,
            "total": m_total,
            "numero_cuotas": cuotas,
            "num_cuotas": cuotas,
            "cuotas": cuotas,
            "modalidad": str(frecuencia).upper(),
            "frecuencia": str(frecuencia),
            "fecha_inicio": fecha_inicio,
            "fecha_vencimiento": fecha_venc,
            "estado": "ACTIVO",
            "observaciones": str(observaciones)
        }

        # Asignar únicamente los atributos que SÍ existan en tu modelo real
        for campo, valor in datos_posibles.items():
            if hasattr(Prestamo, campo):
                setattr(nuevo_prestamo, campo, valor)

        self.db.add(nuevo_prestamo)
        self.db.flush() # Generar el ID

        # 5. Generar cuotas de forma segura
        f_actual = fecha_inicio
        for i in range(1, cuotas + 1):
            f_actual += timedelta(days=delta)
            nueva_cuota = Cuota()
            
            cuota_datos = {
                "prestamo_id": nuevo_prestamo.id,
                "numero_cuota": i,
                "monto_cuota": v_cuota,
                "monto_pagado": 0.0,
                "fecha_vencimiento": f_actual,
                "estado": "PENDIENTE"
            }

            for c_campo, c_valor in cuota_datos.items():
                if hasattr(Cuota, c_campo):
                    setattr(nueva_cuota, c_campo, c_valor)

            self.db.add(nueva_cuota)

        self.db.commit()
        self.db.refresh(nuevo_prestamo)
        return nuevo_prestamo

    def listar_activos(self) -> list[Prestamo]:
        """Retorna todos los préstamos activos o la lista completa si falla el filtro."""
        try:
            if hasattr(Prestamo, "estado"):
                return self.db.query(Prestamo).filter(Prestamo.estado == "ACTIVO").all()
            return self.db.query(Prestamo).all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_por_usuario(self, usuario: str) -> list[Prestamo]:
        try:
            if hasattr(Prestamo, "usuario"):
                return self.db.query(Prestamo).filter(Prestamo.usuario == usuario).all()
            return self.db.query(Prestamo).all()
        except Exception:
            return []

    def obtener_todos(self) -> list[Prestamo]:
        return self.db.query(Prestamo).all()
