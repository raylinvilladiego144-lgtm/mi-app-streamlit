"""
prestamo_repository.py
Repositorio con validación para evitar duplicar préstamos idénticos al mismo cliente 
y motor de recálculo por temporalidad y vencimiento mensual.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota, EstadoPrestamo, ModalidadInteres, EstadoCuota
from cliente import Cliente


class PrestamoRepository:
    """
    Repositorio optimizado para la gestión de préstamos, cuotas y recálculos por temporalidad mensual.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_prestamo(
        self,
        cliente_id: int | None = None,
        cliente_nombre: str | None = None,
        capital: float | Decimal = 0.0,
        tasa_interes: float | Decimal = 0.0,
        num_cuotas: int = 1,
        frecuencia: str = "FIJO",
        fecha_inicio=None,
        observaciones: str = "",
        usuario: str = "admin",
    ) -> Prestamo:
        """
        Crea un nuevo préstamo validando que no exista uno idéntico activo para el cliente.
        Soporta tanto 'cliente_id' directo como 'cliente_nombre' para mantener compatibilidad total.
        """
        cliente_obj = None

        # 1. Si se proporciona cliente_id, buscar directamente por ID
        if cliente_id is not None:
            cliente_obj = self.db.query(Cliente).filter(Cliente.id == cliente_id).first()

        # 2. Si no se encontró por ID o se envió cliente_nombre, resolver por nombre
        if not cliente_obj:
            if not cliente_nombre:
                raise ValueError("Error: Debes ingresar un ID de cliente válido o el nombre completo del cliente.")
            
            nombre_limpio = str(cliente_nombre).strip()
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

        cap_dec = Decimal(str(capital or 0.0))
        tasa_dec = Decimal(str(tasa_interes or 0.0)) / Decimal("100")
        cuotas_totales = int(num_cuotas or 1)

        # Validación opcional: Verificar si ya tiene un préstamo activo exactamente igual
        prestamo_existente = self.db.query(Prestamo).filter(
            Prestamo.cliente_id == cliente_obj.id,
            Prestamo.capital == cap_dec,
            Prestamo.porcentaje_interes == Decimal(str(tasa_interes or 0.0)),
            Prestamo.estado == EstadoPrestamo.ACTIVO
        ).first()

        if prestamo_existente:
            return prestamo_existente  # Retorna el existente en lugar de duplicarlo

        if fecha_inicio is None:
            fecha_inicio = datetime.now().date()
        elif isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()

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

    def evaluar_y_recalcular_temporalidad_mensual(self, usuario: str = None):
        """
        Motor de temporalidad: Recorre los préstamos activos y verifica si cuotas pendientes
        han cruzado fuera del rango del mes en curso (comparando año/mes de fecha_pago_esperada 
        con la fecha actual). Si están vencidas fuera del rango mensual, se les recalcula 
        el interés pendiente aplicando el mismo porcentaje original pactado.
        """
        query = self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO)
        if usuario:
            query = query.filter(Prestamo.usuario == usuario)
        
        prestamos_activos = query.all()
        hoy = datetime.now().date()

        for p in prestamos_activos:
            tasa_porcentual = p.porcentaje_interes or Decimal("0.0")
            if tasa_porcentual <= 0:
                continue
            tasa_dec = tasa_porcentual / Decimal("100")

            cuotas_pendientes = [
                c for c in p.cuotas 
                if c.estado in [EstadoCuota.PENDIENTE, EstadoCuota.PARCIAL] and c.fecha_pago_esperada
            ]

            for cuota in cuotas_pendientes:
                # Comprobar si la fecha esperada está en un mes/año anterior al actual (fuera de rango mensual)
                if cuota.fecha_pago_esperada < hoy:
                    # Validar si ya cruzó un cambio de mes completo fuera del rango original
                    if (hoy.year > cuota.fecha_pago_esperada.year) or \
                       (hoy.year == cuota.fecha_pago_esperada.year and hoy.month > cuota.fecha_pago_esperada.month):
                        
                        saldo_pendiente_cuota = cuota.monto_cuota - (cuota.monto_pagado or Decimal("0.00"))
                        
                        # Evitar recálculos duplicados masivos en el mismo mes si ya fue ajustado
                        marca_recalculo = f"[Recalculado Mes {hoy.month}/{hoy.year}]"
                        obs_actual = getattr(cuota, "observaciones", "") or ""
                        
                        if marca_recalculo not in obs_actual:
                            # Recálculo del interés sobre el saldo vencido usando el mismo % original
                            interes_adicional = saldo_pendiente_cuota * tasa_dec
                            cuota.monto_cuota += interes_adicional
                            p.monto_total += interes_adicional
                            
                            cuota.observaciones = f"{obs_actual} {marca_recalculo}".strip()
                            self.db.add(cuota)
                            self.db.add(p)

        self.db.commit()

    def listar_activos(self) -> list[Prestamo]:
        try:
            self.evaluar_y_recalcular_temporalidad_mensual()
            return self.db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO).all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_por_usuario(self, usuario: str) -> list[Prestamo]:
        try:
            self.evaluar_y_recalcular_temporalidad_mensual(usuario=usuario)
            return self.db.query(Prestamo).filter(Prestamo.usuario == usuario).all()
        except Exception:
            return self.db.query(Prestamo).all()

    def obtener_todos(self) -> list[Prestamo]:
        return self.db.query(Prestamo).all()
