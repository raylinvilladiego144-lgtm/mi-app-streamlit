"""
prestamo_service.py
Servicio de lógica de negocio para la creación y gestión de préstamos.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import streamlit as st  # ⚡ Importado para refrescar la interfaz de forma instantánea
from prestamo_repository import PrestamoRepository
from prestamo import EstadoCuota, EstadoPrestamo, Prestamo, Cuota
from evento import EventoFinanciero, TipoEvento
from caja_service import CajaService


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

        # Mapeo de frecuencia numérica a descriptor de texto para el repositorio
        frecuencia_str = "FIJO"
        if delta_dias == 1:
            frecuencia_str = "DIARIO"
        elif delta_dias == 7:
            frecuencia_str = "SEMANAL"
        elif delta_dias == 15:
            frecuencia_str = "QUINCENAL"
        elif delta_dias >= 28:
            frecuencia_str = "MENSUAL"

        nuevo_prestamo = self.repo.crear_prestamo(
            cliente_id=c_id,
            capital=cap_dec,
            tasa_interes=porcentaje_interes,
            num_cuotas=num_cuotas_int,
            frecuencia=frecuencia_str,
            fecha_inicio=fecha_inicio,
            observaciones=observaciones,
            usuario=usuario
        )

        return nuevo_prestamo

    def verificar_liquidacion(self, prestamo: Prestamo) -> bool:
        """
        Calcula el saldo pendiente real del préstamo (monto_total - total pagado
        en todas sus cuotas) y lo marca como LIQUIDADO si ya no queda deuda,
        sin importar desde qué módulo se registraron los pagos (Pago Inteligente,
        módulo de Pagos en efectivo, etc.). No modifica cuotas, montos ni
        historial: únicamente actualiza el campo 'estado' del préstamo cuando
        corresponde.
        """
        if prestamo.estado != EstadoPrestamo.ACTIVO:
            return False

        total_pagado = sum((c.monto_pagado or Decimal("0.00")) for c in prestamo.cuotas)
        saldo_pendiente = (prestamo.monto_total or Decimal("0.00")) - total_pagado

        if saldo_pendiente <= Decimal("0.01"):  # tolerancia por redondeo
            prestamo.estado = EstadoPrestamo.LIQUIDADO
            self.db.add(prestamo)
            return True
        return False

    def refinanciar_prestamo(
        self,
        prestamo_id: int,
        nuevo_capital: float | Decimal,
        nueva_tasa: float | Decimal,
        nuevo_plazo: int,
        nueva_fecha_vencimiento=None,
        observacion: str = "",
        usuario: str = "admin"
    ):
        """
        Ejecuta la refinanciación de un préstamo existente asegurando el cálculo 
        correcto del monto_interes para evitar IntegrityError en la base de datos.
        """
        current_user = str(usuario or "admin").strip().lower()

        prestamo_anterior = self.db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == current_user
        ).first()

        if not prestamo_anterior:
            raise ValueError("El préstamo a refinanciar no existe o no pertenece al usuario activo.")

        total_abonado_previo = sum(
            (c.monto_pagado or Decimal("0.00")) for c in prestamo_anterior.cuotas
        )

        prestamo_anterior.estado = EstadoPrestamo.REFINANCIADO if hasattr(EstadoPrestamo, 'REFINANCIADO') else EstadoPrestamo.LIQUIDADO
        self.db.add(prestamo_anterior)

        capital_dec = Decimal(str(nuevo_capital or 0.0))
        
        tasa_dec = Decimal(str(nueva_tasa)) / Decimal("100")
        monto_interes_calculado = capital_dec * tasa_dec
        nuevo_monto_total = capital_dec + monto_interes_calculado
        
        num_cuotas = int(nuevo_plazo or 1)
        valor_cuota = nuevo_monto_total / Decimal(str(num_cuotas))

        if nueva_fecha_vencimiento is None:
            fecha_base = datetime.now().date()
        elif isinstance(nueva_fecha_vencimiento, str):
            fecha_base = datetime.strptime(nueva_fecha_vencimiento, "%Y-%m-%d").date()
        else:
            fecha_base = nueva_fecha_vencimiento

        nuevo_prestamo = Prestamo(
            cliente_id=prestamo_anterior.cliente_id,
            capital=capital_dec,
            porcentaje_interes=nueva_tasa,
            monto_interes=monto_interes_calculado,
            monto_total=nuevo_monto_total,
            numero_cuotas=num_cuotas,
            fecha_inicio=datetime.now().date(),
            fecha_vencimiento=fecha_base,
            estado=EstadoPrestamo.ACTIVO,
            usuario=current_user,
            observaciones=f"Refinanciación de Préstamo #{prestamo_anterior.id}. {observacion}".strip()
        )
        self.db.add(nuevo_prestamo)
        self.db.flush()

        intervalo_dias = 30 // num_cuotas if num_cuotas <= 30 else 1
        for i in range(1, num_cuotas + 1):
            fecha_esperada = datetime.now().date() + timedelta(days=i * max(intervalo_dias, 1))
            nueva_cuota = Cuota(
                prestamo_id=nuevo_prestamo.id,
                numero_cuota=i,
                monto_cuota=valor_cuota,
                monto_pagado=Decimal("0.00"),
                fecha_pago_esperada=fecha_esperada,
                estado=EstadoCuota.PENDIENTE
            )
            self.db.add(nueva_cuota)

        # Saldo realmente adeudado del préstamo anterior (lo que falta por pagar,
        # NO lo que ya se abonó). Solo el excedente sobre esa deuda es efectivo
        # nuevo que sale de caja; la porción que cubre la deuda anterior es una
        # conversión de deuda a deuda y no debe mover caja.
        monto_total_anterior = prestamo_anterior.monto_total or Decimal("0.00")
        saldo_pendiente_anterior = monto_total_anterior - total_abonado_previo
        if saldo_pendiente_anterior < Decimal("0.00"):
            saldo_pendiente_anterior = Decimal("0.00")

        desembolso_neto_caja = capital_dec - saldo_pendiente_anterior
        if desembolso_neto_caja < Decimal("0.00"):
            desembolso_neto_caja = Decimal("0.00")

        if desembolso_neto_caja > Decimal("0.00"):
            caja_service = CajaService(self.db, usuario_actual=current_user)
            obs_caja = f"Desembolso neto por refinanciación (Préstamo #{nuevo_prestamo.id} absorbe #{prestamo_anterior.id})"
            caja_service.registrar_retiro(monto=desembolso_neto_caja, observacion=obs_caja)

        evento = EventoFinanciero(
            tipo_evento=TipoEvento.RENOVACION_REALIZADA if hasattr(TipoEvento, 'RENOVACION_REALIZADA') else TipoEvento.CREACION,
            monto=nuevo_monto_total,
            usuario=current_user,
            observacion=f"Refinanciación aplicada del Préstamo #{prestamo_anterior.id} al #{nuevo_prestamo.id}",
            creado_en=datetime.now()
        )
        self.db.add(evento)
        self.db.commit()

        st.cache_data.clear()
        return nuevo_prestamo

    def registrar_pago_inteligente(
        self,
        prestamo_id: int,
        monto_pagado: float | Decimal,
        usuario_actual: str = "admin",
        observacion: str = "",
        registrar_en_caja: bool = True
    ) -> EventoFinanciero:
        """
        Registra un pago de forma inteligente distribuyendo el dinero en las cuotas pendientes.
        Permite condicionar el impacto en caja de forma limpia y sin duplicidades.
        """
        current_user = str(usuario_actual or "admin").strip().lower()
        
        prestamo = self.db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == current_user
        ).first()
        
        if not prestamo:
            raise ValueError("El préstamo seleccionado no existe o no pertenece al usuario activo.")

        monto_restante = Decimal(str(monto_pagado or 0.0))
        if monto_restante <= Decimal("0.00"):
            raise ValueError("El monto del pago debe ser mayor a cero.")
        
        cuotas_pendientes = [
            c for c in prestamo.cuotas 
            if c.estado != EstadoCuota.PAGADA
        ]
        cuotas_pendientes.sort(key=lambda x: x.numero_cuota if hasattr(x, 'numero_cuota') else x.id)

        if not cuotas_pendientes:
            raise ValueError("Este préstamo ya se encuentra totalmente cancelado o no tiene cuotas pendientes.")

        total_abonado_efectivo = Decimal("0.00")
        cuotas_afectadas = []

        for cuota in cuotas_pendientes:
            if monto_restante <= Decimal("0.00"):
                break

            monto_ya_pagado = cuota.monto_pagado or Decimal("0.00")
            saldo_pendiente_cuota = cuota.monto_cuota - monto_ya_pagado

            if monto_restante >= saldo_pendiente_cuota:
                monto_restante -= saldo_pendiente_cuota
                cuota.monto_pagado = cuota.monto_cuota
                cuota.estado = EstadoCuota.PAGADA
                total_abonado_efectivo += saldo_pendiente_cuota
            else:
                cuota.monto_pagado = monto_ya_pagado + monto_restante
                cuota.estado = EstadoCuota.PARCIAL if hasattr(EstadoCuota, 'PARCIAL') else EstadoCuota.PENDIENTE
                total_abonado_efectivo += monto_restante
                monto_restante = Decimal("0.00")

            cuota.fecha_pago_real = datetime.now().date()
            self.db.add(cuota)
            cuotas_afectadas.append(str(cuota.numero_cuota))

        if monto_restante > Decimal("0.00"):
            total_abonado_efectivo += monto_restante

        detalle_cuotas_str = ", ".join(cuotas_afectadas)
        obs_caja = f"Pago distribuido en cuota(s) #{detalle_cuotas_str} (Préstamo #{prestamo.id}). {observacion}".strip()

        self.db.flush()
        self.verificar_liquidacion(prestamo)

        # Impacto único y limpio en caja: un solo evento PAGO_RECIBIDO, sin duplicidad.
        # (Antes se llamaba también a caja_service.registrar_ingreso() sin especificar
        # 'tipo', lo que caía en su valor por defecto APORTE_CAJA y generaba un
        # segundo evento fantasma con el mismo monto. Ahora solo se usa el método
        # oficial diseñado para pagos de cuota.)
        evento = None
        if registrar_en_caja and total_abonado_efectivo > Decimal("0.00"):
            caja_service = CajaService(self.db, usuario_actual=current_user)
            evento = caja_service.registrar_pago_cuota(
                monto=total_abonado_efectivo,
                observacion=obs_caja,
                prestamo_id=prestamo.id
            )
        else:
            self.db.commit()

        st.cache_data.clear()
        return evento
