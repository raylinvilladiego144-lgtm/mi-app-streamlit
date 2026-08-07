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

        desembolso_neto_caja = capital_dec - total_abonado_previo
        if desembolso_neto_caja < Decimal("0.00"):
            desembolso_neto_caja = Decimal("0.00")

        if desembolso_neto_caja > Decimal("0.00"):
            caja_service = CajaService(self.db, usuario_actual=current_user)
            obs_caja = f"Desembolso neto por refinanciación (Préstamo #{nuevo_prestamo.id} absorbe #{prestamo_anterior.id})"
            
            for metodo_caja in ["registrar_egreso", "registrar_salida", "egresar", "retirar"]:
                if hasattr(caja_service, metodo_caja):
                    try:
                        fn = getattr(caja_service, metodo_caja)
                        try:
                            fn(monto=desembolso_neto_caja, tipo="EGRESO", observacion=obs_caja)
                        except TypeError:
                            try:
                                fn(monto=desembolso_neto_caja, observacion=obs_caja)
                            except TypeError:
                                fn(desembolso_neto_caja)
                        break
                    except Exception:
                        pass

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
        Permite condicionar el impacto en caja (desde Préstamos no afecta la caja; desde Pagos sí).
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

        # Condicional estricto: solo afecta la caja si registrar_en_caja es True
        if registrar_en_caja:
            caja_service = CajaService(self.db, usuario_actual=current_user)
            operacion_exitosa = False
            for metodo_caja in ["registrar_ingreso", "registrar_aporte", "registrar_movimiento", "ingresar"]:
                if hasattr(caja_service, metodo_caja):
                    try:
                        fn = getattr(caja_service, metodo_caja)
                        try:
                            fn(monto=total_abonado_efectivo, tipo="INGRESO", observacion=obs_caja)
                        except TypeError:
                            try:
                                fn(monto=total_abonado_efectivo, observacion=obs_caja)
                            except TypeError:
                                fn(total_abonado_efectivo)
                        operacion_exitosa = True
                        break
                    except Exception:
                        pass

            if not operacion_exitosa and hasattr(caja_service, "caja") and caja_service.caja:
                if hasattr(caja_service.caja, "saldo_disponible"):
                    caja_service.caja.saldo_disponible += total_abonado_efectivo
                    self.db.add(caja_service.caja)

        self.db.flush()
        todas_pagadas = all(c.estado == EstadoCuota.PAGADA for c in prestamo.cuotas)
        if todas_pagadas:
            prestamo.estado = EstadoPrestamo.LIQUIDADO
            self.db.add(prestamo)

        evento = EventoFinanciero(
            tipo_evento=TipoEvento.PAGO_RECIBIDO,
            monto=total_abonado_efectivo,
            usuario=current_user,
            observacion=obs_caja,
            creado_en=datetime.now()
        )

        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)

        st.cache_data.clear()
        return evento
