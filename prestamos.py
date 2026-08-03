"""
prestamos.py
Módulo de gestión de préstamos, cartera activa y creación de nuevos desembolsos.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import streamlit as st

from database import SessionLocal
from prestamo_repository import PrestamoRepository
from cliente_repository import ClienteRepository
from caja_service import CajaService


def render_prestamos():
    st.title("💳 Gestión de Préstamos")
    
    # Pestañas para alternar entre ver la cartera o crear uno nuevo
    tab_cartera, tab_nuevo = st.tabs(["📂 Cartera Activa", "➕ Nuevo Préstamo"])

    db = SessionLocal()
    try:
        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)
        usuario_actual = st.session_state.get("username", "admin")

        # --- PESTAÑA 1: CARTERA ACTIVA ---
        with tab_cartera:
            st.subheader("📋 Préstamos Activos en Curso")
            prestamos = prestamo_repo.obtener_por_usuario(usuario_actual)

            if not prestamos:
                st.info("No hay préstamos activos registrados.")
            else:
                data = []
                for p in prestamos:
                    # Mostrar únicamente el nombre del cliente
                    nombre_cliente = getattr(p, "cliente_nombre", None)
                    if not nombre_cliente and hasattr(p, "cliente") and p.cliente:
                        nombre_cliente = getattr(p.cliente, "nombre_completo", "N/A")
                    elif not nombre_cliente:
                        nombre_cliente = "N/A"

                    data.append({
                        "ID": p.id,
                        "Cliente": nombre_cliente,
                        "Capital": f"${p.capital:,.2f}" if hasattr(p, "capital") else "$0.00",
                        "Interés (%)": f"{p.porcentaje_interes}%" if hasattr(p, "porcentaje_interes") else "0%",
                        "Total a Pagar": f"${p.monto_total:,.2f}" if hasattr(p, "monto_total") else "$0.00",
                        "Cuotas": getattr(p, "numero_cuotas", 1),
                        "Estado": getattr(p, "estado", "ACTIVO")
                    })

                df_prestamos = pd.DataFrame(data)
                st.dataframe(df_prestamos, use_container_width=True, hide_index=True)

        # --- PESTAÑA 2: NUEVO PRÉSTAMO / DESEMBOLSO ---
        with tab_nuevo:
            st.subheader("Nuevo Desembolso")

            clientes = cliente_repo.obtener_por_usuario(usuario_actual)

            if not clientes:
                st.warning("⚠️ No tienes clientes registrados. Por favor, ve al módulo de 'Clientes' y registra al menos uno antes de otorgar un préstamo.")
                return

            # Mapeo directo para mostrar ÚNICAMENTE el nombre completo del cliente en el selectbox
            clientes_dict = {c.nombre_completo: c for c in clientes if hasattr(c, "nombre_completo")}

            if not clientes_dict:
                st.warning("⚠️ Los clientes registrados no tienen un nombre válido asignado.")
                return

            with st.form("form_nuevo_prestamo"):
                col_c1, col_c2 = st.columns(2)

                with col_c1:
                    cliente_seleccionado_nombre = st.selectbox(
                        "Seleccionar Cliente *",
                        options=list(clientes_dict.keys())
                    )
                    
                    capital = st.number_input(
                        "Capital a prestar ($) *",
                        min_value=0.0,
                        value=1000.0,
                        step=100.0
                    )

                    tasa_interes = st.number_input(
                        "Tasa de interés (%) *",
                        min_value=0.0,
                        value=20.0,
                        step=1.0
                    )

                    frecuencia = st.selectbox(
                        "Frecuencia de pago *",
                        ["Diario", "Semanal", "Quincenal", "Mensual"]
                    )

                with col_c2:
                    num_cuotas = st.number_input(
                        "Número de cuotas *",
                        min_value=1,
                        value=4,
                        step=1
                    )

                    fecha_inicio = st.date_input(
                        "Fecha de inicio / primer cobro *",
                        value=datetime.now().date()
                    )

                    # Cálculo de simulación visual en tiempo real dentro del formulario
                    cap_sim = Decimal(str(capital))
                    tasa_sim = Decimal(str(tasa_interes)) / Decimal("100")
                    total_cobrar_sim = cap_sim + (cap_sim * tasa_sim)
                    cuotas_sim = int(num_cuotas) if num_cuotas > 0 else 1
                    valor_cuota_sim = total_cobrar_sim / Decimal(str(cuotas_sim))

                    st.markdown(
                        f"""
                        💡 **Simulación:** Total a cobrar: **${total_cobrar_sim:,.2f}** | Valor cuota aprox: **${valor_cuota_sim:,.2f}**
                        """,
                        unsafe_allow_html=True
                    )

                observaciones = st.text_area(
                    "Observaciones o notas adicionales",
                    placeholder="Ej. Garantía entregada, condiciones especiales..."
                )

                submitted = st.form_submit_button("💰 Confirmar y Crear Préstamo", use_container_width=True, type="primary")

                if submitted:
                    cliente_obj = clientes_dict.get(cliente_seleccionado_nombre)
                    if not cliente_obj:
                        st.error("❌ Error: Selecciona un cliente válido.")
                    else:
                        try:
                            caja_service = CajaService(db, usuario_actual=usuario_actual)
                            resumen_caja = caja_service.obtener_resumen_financiero()
                            caja_disponible = Decimal(str(resumen_caja.get("caja_disponible", 0.0)))

                            if Decimal(str(capital)) > caja_disponible:
                                st.error(f"❌ Fondos insuficientes en caja. Caja disponible: ${caja_disponible:,.2f}")
                            else:
                                prestamo_repo.crear_prestamo(
                                    cliente_nombre=cliente_obj.nombre_completo,
                                    capital=capital,
                                    tasa_interes=tasa_interes,
                                    num_cuotas=num_cuotas,
                                    frecuencia=frecuencia,
                                    fecha_inicio=fecha_inicio,
                                    observaciones=observaciones,
                                    usuario=usuario_actual
                                )
                                st.success(f"¡Préstamo a '{cliente_obj.nombre_completo}' creado con éxito!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al procesar el préstamo: {e}")

    finally:
        db.close()
