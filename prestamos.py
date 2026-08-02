"""
app/pages/prestamos.py

Módulo de gestión de préstamos.
Consulta préstamos activos, historial y creación de nuevos préstamos.
"""

from datetime import date
from decimal import Decimal

import streamlit as st

from app.database.database import SessionLocal
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository
from app.services.prestamo_service import PrestamoService


def render_prestamos():
    st.markdown("## 📄 Gestión de Préstamos")
    st.caption("Administración de desembolsos, estados, cartera activa e historial")

    db = SessionLocal()

    try:
        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)
        prestamo_service = PrestamoService(db)

        # ==========================
        # MÉTRICAS GENERALES
        # ==========================
        prestamos_activos = prestamo_repo.listar_activos()

        capital_colocado = sum(
            (p.capital for p in prestamos_activos),
            Decimal("0.00")
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="📄 Préstamos Activos",
                value=len(prestamos_activos)
            )

        with col2:
            st.metric(
                label="💰 Capital Prestado",
                value=f"${capital_colocado:,.2f}"
            )

        with col3:
            st.metric(
                label="📊 Estado del Módulo",
                value="Operativo"
            )

        st.divider()

        # ==========================
        # PESTAÑAS
        # ==========================
        tab_lista, tab_nuevo = st.tabs(
            [
                "📋 Cartera Activa",
                "➕ Nuevo Préstamo"
            ]
        )

        # ==========================
        # LISTADO DE PRÉSTAMOS
        # ==========================
        with tab_lista:
            st.subheader("Préstamos Vigentes")

            if not prestamos_activos:
                st.info("No existen préstamos activos en este momento.")
            else:
                clientes_dict = {c.id: c for c in cliente_repo.listar_todos()}

                for prestamo in prestamos_activos:
                    cliente = clientes_dict.get(prestamo.cliente_id)
                    nombre_cliente = cliente.nombre_completo if cliente else "Cliente no encontrado"

                    with st.container():
                        col_info, col_valor, col_estado = st.columns([3, 2, 2])

                        with col_info:
                            st.markdown(f"### 👤 {nombre_cliente}")
                            st.caption(f"**ID Préstamo:** #{prestamo.id}")
                            st.caption(f"**Fecha inicio:** {prestamo.fecha_inicio}")

                        with col_valor:
                            st.metric(
                                label="Capital Original",
                                value=f"${prestamo.capital:,.2f}"
                            )
                            st.caption(f"Total a pagar: **${prestamo.monto_total:,.2f}**")

                        with col_estado:
                            estado_val = prestamo.estado.value if hasattr(prestamo.estado, 'value') else str(prestamo.estado)
                            st.markdown(f"Estado: `:green[{estado_val}]`" if "ACTIVO" in estado_val.upper() else f"Estado: **{estado_val}**")
                            st.caption(f"Número de cuotas: **{prestamo.numero_cuotas}**")

                        st.divider()

        # ==========================
        # CREAR PRÉSTAMO
        # ==========================
        with tab_nuevo:
            st.subheader("Nuevo Desembolso")

            clientes = cliente_repo.listar_todos()

            if not clientes:
                st.warning("⚠️ No hay clientes registrados. Debe registrar al menos un cliente antes de crear un préstamo.")
            else:
                with st.form("form_crear_prestamo", clear_on_submit=False):
                    cliente_seleccionado = st.selectbox(
                        "Seleccionar Cliente *",
                        options=clientes,
                        format_func=lambda x: f"{x.nombre_completo} — Doc: {x.documento}"
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        capital = st.number_input(
                            "Capital a prestar ($) *",
                            min_value=100.0,
                            value=1000.0,
                            step=100.0,
                            format="%.2f"
                        )

                        interes = st.number_input(
                            "Tasa de interés (%) *",
                            min_value=0.0,
                            max_value=100.0,
                            value=20.0,
                            step=0.5,
                            format="%.2f"
                        )

                        frecuencia = st.selectbox(
                            "Frecuencia de pago *",
                            options=[
                                ("Diario", 1),
                                ("Semanal", 7),
                                ("Quincenal", 15),
                                ("Mensual", 30)
                            ],
                            format_func=lambda x: x[0],
                            index=1
                        )

                    with col2:
                        cuotas = st.number_input(
                            "Número de cuotas *",
                            min_value=1,
                            max_value=120,
                            value=4,
                            step=1
                        )

                        fecha_inicio = st.date_input(
                            "Fecha de inicio / primer cobro *",
                            value=date.today()
                        )

                        monto_interes = Decimal(str(capital)) * (Decimal(str(interes)) / Decimal("100"))
                        monto_total_est = Decimal(str(capital)) + monto_interes
                        valor_cuota_est = monto_total_est / Decimal(str(cuotas))

                        st.info(
                            f"💡 **Simulación:** Total a cobrar: **${monto_total_est:,.2f}** "
                            f"| Valor cuota aprox: **${valor_cuota_est:,.2f}**"
                        )

                    observacion = st.text_area(
                        "Observaciones o notas adicionales",
                        placeholder="Ej. Garantía entregada, condiciones especiales...",
                        height=80
                    )

                    guardar = st.form_submit_button(
                        "💰 Confirmar y Crear Préstamo",
                        use_container_width=True,
                        type="primary"
                    )

                    if guardar:
                        try:
                            prestamo_service.crear_prestamo(
                                cliente_id=cliente_seleccionado.id,
                                capital=Decimal(str(capital)),
                                porcentaje_interes=Decimal(str(interes)),
                                numero_cuotas=int(cuotas),
                                fecha_inicio=fecha_inicio,
                                frecuencia_dias=frecuencia[1],
                                observaciones=observacion.strip()
                            )

                            st.success("✅ Préstamo creado y registrado correctamente en sistema.")
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al intentar registrar el préstamo: {e}")

    finally:
        db.close()