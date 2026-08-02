"""
app/pages/perfil_cliente.py

Pantalla de detalle del cliente:
- Información general
- Creación de préstamos
- Cronograma de cuotas
- Registro de pagos
"""

import streamlit as st
from decimal import Decimal
from datetime import date

from app.database.database import SessionLocal
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository
from app.services.prestamo_service import PrestamoService
from app.models.prestamo import EstadoCuota


def render_perfil_cliente(cliente_id: int):
    db = SessionLocal()

    try:
        cliente_repo = ClienteRepository(db)
        prestamo_repo = PrestamoRepository(db)
        prestamo_service = PrestamoService(db)

        cliente = cliente_repo.obtener_por_id(cliente_id)

        if not cliente:
            st.error("Cliente no encontrado.")
            if st.button("⬅️ Volver a Clientes"):
                st.session_state.pop("cliente_seleccionado_id", None)
                st.rerun()
            return

        if st.button("⬅️ Volver al Directorio de Clientes"):
            st.session_state.pop("cliente_seleccionado_id", None)
            st.rerun()

        st.divider()

        # ===============================
        # INFORMACIÓN CLIENTE
        # ===============================
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"## 👤 {cliente.nombre_completo}")
            st.caption(f"Documento: {cliente.documento}")
            st.caption(f"Teléfono: {cliente.telefono}")
            if cliente.direccion:
                st.caption(f"Dirección: {cliente.direccion}")

        with col2:
            st.markdown(f"**Estado:** {cliente.estado.value}")
            st.markdown(f"**Calificación:** {cliente.calificacion.value}")

        st.divider()

        # ===============================
        # PRÉSTAMO ACTIVO
        # ===============================
        prestamo = prestamo_repo.obtener_activo_por_cliente(cliente.id)

        if prestamo:
            st.markdown(f"## 📄 Préstamo #{prestamo.id}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Capital", f"${prestamo.capital:,.2f}")
            c2.metric("Total", f"${prestamo.monto_total:,.2f}")
            c3.metric("Interés", f"{prestamo.porcentaje_interes}%")
            c4.metric("Cuotas", prestamo.numero_cuotas)

            st.divider()

            st.subheader("📅 Cronograma")

            for cuota in prestamo.cuotas:
                if cuota.estado == EstadoCuota.PAGADA:
                    estado = "🟢 PAGADA"
                elif cuota.estado == EstadoCuota.PARCIAL:
                    estado = "🟡 PARCIAL"
                else:
                    estado = "🔴 PENDIENTE"

                col1, col2, col3, col4 = st.columns([1, 2, 2, 2])

                with col1:
                    st.write(f"Cuota {cuota.numero_cuota}")

                with col2:
                    st.write(f"${cuota.monto_cuota:,.2f}")

                with col3:
                    st.write(f"Pagado ${cuota.monto_pagado:,.2f}")

                with col4:
                    st.write(estado)

                if cuota.estado != EstadoCuota.PAGADA:
                    with st.expander("💵 Registrar pago"):
                        pendiente = cuota.monto_cuota - cuota.monto_pagado

                        monto = st.number_input(
                            "Monto",
                            min_value=1.0,
                            max_value=float(pendiente),
                            value=float(pendiente),
                            key=f"pago_{cuota.id}",
                        )

                        if st.button("Confirmar pago", key=f"confirmar_{cuota.id}"):
                            try:
                                _, liquidado = prestamo_service.registrar_pago_cuota(
                                    cuota_id=cuota.id,
                                    monto_abonado=Decimal(str(monto)),
                                    usuario=st.session_state.get("usuario", "admin"),
                                )

                                if liquidado:
                                    st.success("🎉 Préstamo liquidado")
                                else:
                                    st.success("Pago registrado")

                                st.rerun()

                            except Exception as error:
                                st.error(str(error))

                st.divider()

        else:
            st.info("Este cliente no tiene préstamos activos.")

            st.subheader("➕ Nuevo préstamo")

            with st.form("nuevo_prestamo"):
                capital = st.number_input("Capital", min_value=100.0, value=1000.0)
                interes = st.number_input("Interés %", min_value=0.0, value=20.0)
                cuotas = st.number_input("Número cuotas", min_value=1, value=4)
                fecha = st.date_input("Fecha inicio", value=date.today())
                observacion = st.text_input("Observación")

                guardar = st.form_submit_button("Crear préstamo", use_container_width=True)

                if guardar:
                    try:
                        prestamo_service.crear_prestamo(
                            cliente_id=cliente.id,
                            capital=Decimal(str(capital)),
                            porcentaje_interes=Decimal(str(interes)),
                            numero_cuotas=int(cuotas),
                            fecha_inicio=fecha,
                            frecuencia_dias=7,
                            observaciones=observacion,
                        )

                        st.success("Préstamo creado correctamente")
                        st.rerun()

                    except Exception as error:
                        st.error(str(error))

    finally:
        db.close()