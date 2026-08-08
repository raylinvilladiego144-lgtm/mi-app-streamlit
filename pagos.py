"""
app/pages/pagos.py

Módulo para el registro y gestión de pagos filtrado por usuario,
integrado con la lógica de caja y distribución inteligente de abonos.
"""

from decimal import Decimal
from datetime import date

import streamlit as st

from app.database.database import SessionLocal
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository
from app.models.prestamo import EstadoCuota, EstadoPrestamo, Prestamo, Cuota
from app.models.evento import EventoFinanciero, TipoEvento
from app.services.caja_service import CajaService


def render_pagos(usuario_actual: str = "admin"):
    current_user = str(usuario_actual or "admin").strip().lower()

    st.markdown(f"## 💳 Registro de Pagos — ({current_user.capitalize()})")
    st.caption("Gestiona los cobros de cuotas, abonos y amortización inteligente")

    db = SessionLocal()

    try:
        cliente_repo = ClienteRepository(db)
        
        # Consultar préstamos activos filtrados por usuario
        query_prestamos = db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO)
        if hasattr(Prestamo, "usuario"):
            query_prestamos = query_prestamos.filter(Prestamo.usuario == current_user)

        prestamos_activos = query_prestamos.all()

        if not prestamos_activos:
            st.info("ℹ️ No tienes préstamos activos pendientes de cobro en este momento.")
            return

        clientes_dict = {c.id: c for c in cliente_repo.listar_todos()}

        opciones_prestamo = {}
        for p in prestamos_activos:
            cliente = clientes_dict.get(p.cliente_id)
            nombre = cliente.nombre_completo if cliente else f"Cliente #{p.cliente_id}"
            capital_val = getattr(p, "capital", getattr(p, "monto_total", Decimal("0.00")))
            label = f"Préstamo #{p.id} - {nombre} (Monto: ${capital_val:,.2f})"
            opciones_prestamo[label] = p

        prestamo_seleccionado_label = st.selectbox(
            "Seleccione el préstamo a abonar *",
            options=list(opciones_prestamo.keys())
        )

        prestamo_actual = opciones_prestamo[prestamo_seleccionado_label]
        cliente_actual = clientes_dict.get(prestamo_actual.cliente_id)

        st.divider()

        col_cli, col_monto, col_estado = st.columns(3)

        with col_cli:
            st.markdown(f"**Cliente:** {cliente_actual.nombre_completo if cliente_actual else 'N/A'}")
            st.caption(f"Documento: {cliente_actual.documento if cliente_actual else 'N/A'}")

        with col_monto:
            monto_tot = getattr(prestamo_actual, 'monto_total', Decimal('0.00'))
            cap_val = getattr(prestamo_actual, 'capital', monto_tot)
            int_val = getattr(prestamo_actual, 'porcentaje_interes', 0.0)
            st.markdown(f"**Monto Total:** ${monto_tot:,.2f}")
            st.caption(f"Capital: ${cap_val:,.2f} | Interés: {int_val}%")

        with col_estado:
            num_ctas = getattr(prestamo_actual, 'numero_cuotas', len(prestamo_actual.cuotas))
            fec_ini = getattr(prestamo_actual, 'fecha_inicio', 'N/A')
            st.markdown(f"**Cuotas Totales:** {num_ctas}")
            st.caption(f"Fecha Inicio: {fec_ini}")

        st.markdown("---")
        st.subheader("📋 Tabla de Cuotas y Estado de Cartera")

        cuotas_pendientes = [c for c in prestamo_actual.cuotas if c.estado != EstadoCuota.PAGADA]

        if not cuotas_pendientes:
            st.success("🎉 ¡Todas las cuotas de este préstamo han sido pagadas!")
        else:
            datos_tabla = []
            for c in sorted(prestamo_actual.cuotas, key=lambda x: x.numero_cuota):
                pendiente = c.monto_cuota - (c.monto_pagado or Decimal("0.00"))
                datos_tabla.append({
                    "Cuota #": c.numero_cuota,
                    "Fecha Vencimiento": getattr(c, "fecha_pago_esperada", "N/A"),
                    "Monto Cuota": f"${c.monto_cuota:,.2f}",
                    "Monto Pagado": f"${c.monto_pagado or Decimal('0.00'):,.2f}",
                    "Saldo Pendiente": f"${pendiente:,.2f}",
                    "Estado": c.estado.value if hasattr(c.estado, 'value') else str(c.estado)
                })

            st.dataframe(datos_tabla, use_container_width=True, hide_index=True)

            st.subheader("💵 Registrar Nuevo Abono (Distribución Inteligente)")

            with st.form("form_registrar_pago", clear_on_submit=True):
                st.markdown("El monto ingresado se distribuirá cronológicamente a través de las cuotas pendientes.")

                col_pago1, col_pago2 = st.columns(2)

                with col_pago1:
                    monto_a_pagar = st.number_input(
                        "Monto del Abono ($) *",
                        min_value=1.0,
                        value=25000.0,
                        step=1000.0,
                        format="%.2f"
                    )

                with col_pago2:
                    fecha_pago = st.date_input("Fecha del Pago *", value=date.today())

                observacion = st.text_input("Observación / Referencia (Opcional)", placeholder="Ej. Abono en efectivo recibido en oficina")

                btn_pagar = st.form_submit_button("💰 Registrar y Aplicar Abono", type="primary", use_container_width=True)

                if btn_pagar:
                    monto_decimal = Decimal(str(monto_a_pagar))
                    monto_restante = monto_decimal

                    cuotas_por_pagar = db.query(Cuota).filter(
                        Cuota.prestamo_id == prestamo_actual.id,
                        Cuota.estado.in_([EstadoCuota.PENDIENTE, EstadoCuota.PARCIAL])
                    ).order_by(Cuota.numero_cuota.asc()).all()

                    if not cuotas_por_pagar:
                        raise ValueError("No hay cuotas pendientes para aplicar este abono.")

                    cuotas_afectadas = []

                    for cuota in cuotas_por_pagar:
                        if monto_restante <= 0:
                            break

                        saldo_pendiente_cuota = cuota.monto_cuota - (cuota.monto_pagado or Decimal("0.00"))

                        if monto_restante >= saldo_pendiente_cuota:
                            monto_restante -= saldo_pendiente_cuota
                            cuota.monto_pagado = cuota.monto_cuota
                            cuota.estado = EstadoCuota.PAGADA
                        else:
                            cuota.monto_pagado = (cuota.monto_pagado or Decimal("0.00")) + monto_restante
                            cuota.estado = EstadoCuota.PARCIAL
                            monto_restante = Decimal("0.00")

                        cuota.fecha_pago_real = fecha_pago
                        db.add(cuota)
                        cuotas_afectadas.append(cuota.numero_cuota)

                    # Integración limpia a través del CajaService unificado
                    caja_service = CajaService(db, usuario_actual=current_user)
                    detalle_cuotas_str = ", ".join([str(c) for c in cuotas_afectadas])
                    obs_caja = f"Abono aplicado a cuota(s) #{detalle_cuotas_str} (Préstamo #{prestamo_actual.id}). {observacion}".strip()

                    # Llamada limpia al servicio que registra el PAGO_RECIBIDO y afecta caja
                    caja_service.registrar_pago_cuota(
                        monto=monto_decimal, 
                        observacion=obs_caja
                    )

                    # Verificar si todas las cuotas del préstamo han sido liquidadas
                    db.flush()
                    todas_pagadas = all(c.estado == EstadoCuota.PAGADA for c in prestamo_actual.cuotas)
                    if todas_pagadas:
                        prestamo_actual.estado = EstadoPrestamo.LIQUIDADO
                        db.add(prestamo_actual)

                    db.commit()
                    st.cache_data.clear()

                    st.success(f"🎉 ¡Abono de ${monto_decimal:,.2f} aplicado con éxito a la(s) cuota(s) #{detalle_cuotas_str}!")
                    st.rerun()

    except Exception as e:
        db.rollback()
        st.error(f"❌ Error al procesar el módulo de pagos: {e}")
    finally:
        db.close()
