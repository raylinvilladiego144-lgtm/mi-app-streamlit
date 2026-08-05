"""
app/pages/caja.py

Vista y controlador para la gestión de la caja por usuario.
"""

from decimal import Decimal
import streamlit as st

# Importaciones ajustadas según tu estructura
from database.database import SessionLocal
from services.caja_service import CajaService


def render_caja(usuario_actual: str = "admin"):
    st.markdown(f"## 🏦 Gestión de Caja — ({usuario_actual.capitalize()})")
    st.caption("Resumen del estado financiero, flujo de efectivo y auditoría de movimientos")

    db = SessionLocal()

    try:
        caja_service = CajaService(db, usuario_actual=usuario_actual)

        resumen = caja_service.obtener_resumen_financiero()
        saldo_actual = caja_service.obtener_saldo_actual()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(label="💵 Caja Disponible", value=f"${saldo_actual:,.2f}")

        with col2:
            st.metric(label="📈 Capital Prestado", value=f"${resumen['capital_prestado']:,.2f}")

        with col3:
            st.metric(label="🏛️ Capital Total", value=f"${resumen['capital_total']:,.2f}")

        with col4:
            st.metric(
                label="📥 Entradas / Salidas",
                value=f"${resumen['entradas_totales']:,.2f}",
                delta=f"-${resumen['salidas_totales']:,.2f}",
                delta_color="inverse",
            )

        st.divider()

        st.subheader("⚡ Acciones de Caja")
        col_aporte, col_retiro = st.columns(2)

        with col_aporte:
            with st.expander("📥 Registrar Aporte de Capital", expanded=False):
                with st.form("form_aporte", clear_on_submit=True):
                    monto_aporte = st.number_input(
                        "Monto a ingresar ($) *", min_value=1.0, step=1000.0, format="%.2f", key="input_monto_aporte_caja"
                    )
                    obs_aporte = st.text_input(
                        "Observación / Concepto *", placeholder="Ej. Inyección de capital inicial", key="input_obs_aporte_caja"
                    )
                    btn_aporte = st.form_submit_button(
                        "Aportar a Caja", type="primary", use_container_width=True
                    )

                    if btn_aporte:
                        if not obs_aporte.strip():
                            st.error("⚠️ La observación es obligatoria.")
                        else:
                            caja_service.registrar_aporte(
                                monto=Decimal(str(monto_aporte)), observacion=obs_aporte.strip()
                            )
                            st.success("🎉 ¡Aporte registrado con éxito!")
                            st.rerun()

        with col_retiro:
            with st.expander("📤 Registrar Retiro de Caja", expanded=False):
                with st.form("form_retiro", clear_on_submit=True):
                    monto_retiro = st.number_input(
                        "Monto a retirar ($) *", min_value=1.0, step=1000.0, format="%.2f", key="input_monto_retiro_caja"
                    )
                    obs_retiro = st.text_input(
                        "Observación / Concepto *", placeholder="Ej. Retiro de ganancias parciales", key="input_obs_retiro_caja"
                    )
                    btn_retiro = st.form_submit_button(
                        "Retirar de Caja", type="secondary", use_container_width=True
                    )

                    if btn_retiro:
                        if not obs_retiro.strip():
                            st.error("⚠️ La observación es obligatoria.")
                        else:
                            try:
                                caja_service.registrar_retiro(
                                    monto=Decimal(str(monto_retiro)), observacion=obs_retiro.strip()
                                )
                                st.success("🎉 ¡Retiro registrado con éxito!")
                                st.rerun()
                            except ValueError as err:
                                st.error(f"❌ {err}")

        st.divider()

        st.subheader("📜 Historial de Movimientos")

        movimientos = caja_service.listar_movimientos()

        if not movimientos:
            st.info("ℹ️ No hay movimientos registrados en tu historial.")
        else:
            tabla_movimientos = []
            for mov in movimientos:
                tipo = (
                    mov.tipo_evento.value
                    if hasattr(mov.tipo_evento, "value")
                    else str(mov.tipo_evento)
                )

                concepto = (
                    getattr(mov, "observacion", None)
                    or getattr(mov, "observaciones", None)
                    or getattr(mov, "concepto", "Sin detalle")
                )

                fecha = (
                    getattr(mov, "fecha", None)
                    or getattr(mov, "created_at", None)
                    or getattr(mov, "id", "N/A")
                )

                tabla_movimientos.append(
                    {
                        "ID": getattr(mov, "id", "-"),
                        "Fecha / ID": fecha,
                        "Tipo de Evento": tipo,
                        "Monto": f"${mov.monto:,.2f}" if getattr(mov, "monto", None) else "$0.00",
                        "Usuario": getattr(mov, "usuario", usuario_actual),
                        "Observación / Detalle": concepto,
                    }
                )

            st.dataframe(tabla_movimientos, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Ocurrió un error en el módulo de caja: {e}")
        db.rollback()
    finally:
        db.close()
