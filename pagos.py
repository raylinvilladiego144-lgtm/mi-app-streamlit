"""
app/pages/pagos.py

Módulo para el registro y gestión de pagos filtrado por usuario.
"""

from decimal import Decimal
from datetime import date

import streamlit as st

from app.database.database import SessionLocal
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository
from app.models.prestamo import EstadoCuota, EstadoPrestamo, Prestamo
from app.models.evento import EventoFinanciero, TipoEvento


def render_pagos(usuario_actual: str = "admin"):
    st.markdown(f"## 💳 Registro de Pagos — ({usuario_actual.capitalize()})")
    st.caption("Gestiona los cobros de cuotas y abonos")

    db = SessionLocal()

    try:
        cliente_repo = ClienteRepository(db)
        
        # Consultar préstamos activos filtrados por usuario
        query_prestamos = db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO)
        if hasattr(Prestamo, "usuario"):
            query_prestamos = query_prestamos.filter(Prestamo.usuario == usuario_actual)

        prestamos_activos = query_prestamos.all()

        if not prestamos_activos:
            st.info("ℹ️ No tienes préstamos activos pendientes de cobro en este momento.")
            return

        clientes_dict = {c.id: c for c in cliente_repo.listar_todos()}

        opciones_prestamo = {}
        for p in prestamos_activos:
            cliente = clientes_dict.get(p.cliente_id)
            nombre = cliente.nombre_completo if cliente else f"Cliente #{p.cliente_id}"
            label = f"Préstamo #{p.id} - {nombre} (Capital: ${p.capital:,.2f})"
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
            st.markdown(f"**Monto Total:** ${prestamo_actual.monto_total:,.2f}")
            st.caption(f"Capital: ${prestamo_actual.capital:,.2f} | Interés: {prestamo_actual.porcentaje_interes}%")

        with col_estado:
            st.markdown(f"**Cuotas Totales:** {prestamo_actual.numero_cuotas}")
            st.caption(f"Fecha Inicio: {prestamo_actual.fecha_inicio}")

        st.markdown("---")
        st.subheader("📋 Tabla de Cuotas")

        cuotas_pendientes = [c for c in prestamo_actual.cuotas if c.estado != EstadoCuota.PAGADA]

        if not cuotas_pendientes:
            st.success("🎉 ¡Todas las cuotas de este préstamo han sido pagadas!")
        else:
            datos_tabla = []
            for c in sorted(prestamo_actual.cuotas, key=lambda x: x.numero_cuota):
                pendiente = c.monto_cuota - (c.monto_pagado or Decimal("0.00"))
                datos_tabla.append({
                    "Cuota #": c.numero_cuota,
                    "Fecha Vencimiento": c.fecha_pago_esperada,
                    "Monto Cuota": f"${c.monto_cuota:,.2f}",
                    "Monto Pagado": f"${c.monto_pagado:,.2f}",
                    "Saldo Pendiente": f"${pendiente:,.2f}",
                    "Estado": c.estado.value if hasattr(c.estado, 'value') else str(c.estado)
                })

            st.dataframe(datos_tabla, use_container_width=True)

            st.subheader("💵 Registrar Nuevo Abono")

            proxima_cuota = min(cuotas_pendientes, key=lambda x: x.numero_cuota)
            saldo_proxima = proxima_cuota.monto_cuota - (proxima_cuota.monto_pagado or Decimal("0.00"))

            with st.form("form_registrar_pago", clear_on_submit=True):
                st.markdown(
                    f"Abonando a **Cuota #{proxima_cuota.numero_cuota}** "
                    f"(Saldo pendiente de cuota: **${saldo_proxima:,.2f}**)"
                )

                col_pago1, col_pago2 = st.columns(2)

                with col_pago1:
                    monto_a_pagar = st.number_input(
                        "Monto a abonar ($) *",
                        min_value=1.0,
                        max_value=float(saldo_proxima),
                        value=float(saldo_proxima),
                        step=10.0,
                        format="%.2f"
                    )

                with col_pago2:
                    fecha_pago = st.date_input("Fecha del Pago *", value=date.today())

                observacion = st.text_input("Observación / Referencia (Opcional)", placeholder="Ej. Pago en efectivo")

                btn_pagar = st.form_submit_button("✅ Registrar Pago", type="primary", use_container_width=True)

                if btn_pagar:
                    monto_decimal = Decimal(str(monto_a_pagar))

                    proxima_cuota.monto_pagado = (proxima_cuota.monto_pagado or Decimal("0.00")) + monto_decimal
                    proxima_cuota.fecha_pago_real = fecha_pago

                    if proxima_cuota.monto_pagado >= proxima_cuota.monto_cuota:
                        proxima_cuota.estado = EstadoCuota.PAGADA
                    else:
                        proxima_cuota.estado = EstadoCuota.PARCIAL

                    evento = EventoFinanciero(
                        tipo_evento=TipoEvento.PAGO_RECIBIDO,
                        monto=monto_decimal,
                        usuario=usuario_actual,
                        observacion=f"Pago cuota #{proxima_cuota.numero_cuota} préstamo #{prestamo_actual.id}. {observacion}".strip()
                    )
                    db.add(evento)

                    todas_pagadas = all(c.estado == EstadoCuota.PAGADA for c in prestamo_actual.cuotas)
                    if todas_pagadas:
                        prestamo_actual.estado = EstadoPrestamo.LIQUIDADO

                    db.commit()

                    st.success(f"🎉 ¡Pago de ${monto_decimal:,.2f} registrado correctamente!")
                    st.rerun()

    except Exception as e:
        st.error(f"❌ Error al procesar el módulo de pagos: {e}")
        db.rollback()
    finally:
        db.close()