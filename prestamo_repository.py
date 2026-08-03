"""
prestamo_repository.py
Repositorio sincronizado que gestiona el cliente por su nombre de forma compatible.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota, EstadoPrestamo, ModalidadInteres, EstadoCuota
from cliente import Cliente  # Asegúrate de importar tu modelo Cliente


class PrestamoRepository:
    """
    Repositorio optimizado para la gestión de préstamos y cuotas.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_prestamo(
        self,
        cliente_nombre,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "FIJO",
        fecha_inicio=None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Crea un nuevo préstamo asociándolo mediante el nombre del cliente.
        """
        if not cliente_nombre:
            raise ValueError("Error: Debes ingresar o seleccionar el nombre completo del cliente.")

        nombre_limpio = str(cliente_nombre).strip()

        # Buscar si el cliente ya existe en la tabla de clientes por su nombre o crearlo de forma interna
        cliente_obj = self.db.query(Cliente).filter(Cliente.nombre_completo == nombre_limpio).first()
        if not cliente_obj:
            cliente_obj = Cliente(
                nombre_completo=nombre_limpio,
                documento="S/D",
                telefono="S/D",
                direccion="S/D",
                usuario=str(usuario or "admin")
            )
            self.db.add(cliente_obj)
            self.db.flush()

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

        # Usamos cliente_id del objeto cliente creado/encontrado para cumplir con el modelo SQLAlchemy
        nuevo_prestamo = Prestamo(
            cliente_id=cliente_obj.id,
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
