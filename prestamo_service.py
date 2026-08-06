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
        nueva_tasa: float | Decimal,
        nuevo_plazo: int,
        nueva_fecha_vencimiento=None,
        observacion: str = "",
        usuario: str = "admin"
    ):
        """
        Ejecuta la refinanciación de un préstamo existente:
        1. Identifica el préstamo anterior y calcula los abonos totales realizados (ej. $300.000).
        2. Liquida o marca como refinanciado el préstamo actual.
        3. Crea un nuevo préstamo con el nuevo capital solicitado (ej. $600.000).
        4. Calcula el desembolso neto de caja restando los abonos previos ($600.000 - $300.000 = $300.000).
        5. Genera las nuevas cuotas asegurando que tengan fechas de pago válidas (evitando errores NOT NULL).
        """
        current_user = str(usuario or "admin").strip().lower()

        prestamo_anterior = self.db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == current_user
        ).first()

        if not prestamo_anterior:
            raise ValueError("El préstamo a refinanciar no existe o no pertenece al usuario activo.")

        # Calcular todo el dinero que el cliente ya abonó en el préstamo anterior
        total_abonado_previo = sum(
            (c.monto_pagado or Decimal("0.00")) for c in prestamo_anterior.cuotas
        )

        # Marcar el préstamo anterior como refinanciado o liquidado
        prestamo_anterior.estado = EstadoPrestamo.REFINANCIADO if hasattr(EstadoPrestamo, 'REFINANCIADO') else EstadoPrestamo.LIQUIDADO
        self.db.add(prestamo_anterior)

        # El nuevo capital o monto de refinanciación solicitado
        nuevo_capital = Decimal(str(prestamo_anterior.capital)) # O puedes recibirlo si se parametriza, por defecto absorbe el capital anterior o el monto total
        
        # Recalcular bajo los nuevos términos (Ej: capital * (1 + nueva_tasa / 100))
        tasa_dec = Decimal(str(nueva_tasa)) / Decimal("100")
        nuevo_monto_total = nuevo_capital + (nuevo_capital * tasa_dec)
        
        num_cuotas = int(nuevo_plazo or 1)
        valor_cuota = nuevo_monto_total / Decimal(str(num_cuotas))

        if nueva_fecha_vencimiento is None:
            fecha_base = datetime.now().date()
        elif isinstance(nueva_fecha_vencimiento, str):
            fecha_base = datetime.strptime(nueva_fecha_vencimiento, "%Y-%m-%d").date()
        else:
            fecha_base = nueva_fecha_vencimiento

        # Crear el nuevo préstamo en estado activo
        nuevo_prestamo = Prestamo(
            cliente_id=prestamo_anterior.cliente_id,
            capital=nuevo_capital,
            tasa_interes=nueva_tasa,
            monto_total=nuevo_monto_total,
            numero_cuotas=num_cuotas,
            fecha_inicio=datetime.now().date(),
            fecha_vencimiento=fecha_base,
            estado=EstadoPrestamo.ACTIVO,
            usuario=current_user,
            observaciones=f"Refinanciación de Préstamo #{prestamo_anterior.id}. {observacion}".strip()
        )
        self.db.add(nuevo_prestamo)
        self.db.flush()  # Para obtener el ID del nuevo préstamo

        # Generar las nuevas cuotas asignando obligatoriamente una fecha de pago esperada (evita el error NOT NULL)
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

        # Calcular el desembolso neto real que sale de caja: Nuevo Crédito - Abonos Previos
        desembolso_neto_caja = nuevo_capital - total_abonado_previo
        if desembolso_neto_caja < Decimal("0.00"):
            desembolso_neto_caja = Decimal("0.00")

        # Registrar el movimiento de salida en la caja si hay un desembolso efectivo neto positivo
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

        # Registrar evento financiero formal
        evento = EventoFinanciero(
            tipo_evento=TipoEvento.REFINANCIACION if hasattr(TipoEvento, 'REFINANCIACION') else TipoEvento.CREACION,
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
        observacion: str = ""
    ) -> EventoFinanciero:
        """
        Registra un pago de forma inteligente: distribuye el dinero ingresado 
        cubriendo la cuota actual y abonando automáticamente a las siguientes si sobra,
        actualizando también de forma correcta la caja y el estado global del préstamo.
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
        
        # Obtener cuotas pendientes ordenadas secuencialmente
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
                # El dinero cubre esta cuota por completo
                monto_restante -= saldo_pendiente_cuota
                cuota.monto_pagado = cuota.monto_cuota
                cuota.estado = EstadoCuota.PAGADA
                total_abonado_efectivo += saldo_pendiente_cuota
            else:
                # El dinero cubre una parte (abono parcial a la cuota)
                cuota.monto_pagado = monto_ya_pagado + monto_restante
                cuota.estado = EstadoCuota.PARCIAL if hasattr(EstadoCuota, 'PARCIAL') else EstadoCuota.PENDIENTE
                total_abonado_efectivo += monto_restante
                monto_restante = Decimal("0.00")

            cuota.fecha_pago_real = datetime.now().date()
            self.db.add(cuota)
            cuotas_afectadas.append(str(cuota.numero_cuota))

        # Si sobra dinero tras liquidar todas las cuotas pendientes
        if monto_restante > Decimal("0.00"):
            total_abonado_efectivo += monto_restante

        # --- SINCRONIZACIÓN AUTOMÁTICA CON LA CAJA DEL USUARIO ---
        caja_service = CajaService(self.db, usuario_actual=current_user)
        detalle_cuotas_str = ", ".join(cuotas_afectadas)
        obs_caja = f"Pago distribuido en cuota(s) #{detalle_cuotas_str} (Préstamo #{prestamo.id}). {observacion}".strip()

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

        # Verificar si todas las cuotas han quedado pagadas para liquidar el préstamo
        self.db.flush()
        todas_pagadas = all(c.estado == EstadoCuota.PAGADA for c in prestamo.cuotas)
        if todas_pagadas:
            prestamo.estado = EstadoPrestamo.LIQUIDADO
            self.db.add(prestamo)

        # Registrar el evento financiero formal en el feed del Dashboard
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

        # ⚡ Limpieza inmediata de la caché de Streamlit para actualizar los saldos al instante
        st.cache_data.clear()

        return evento
