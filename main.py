"""
main.py
Aplicación principal en Streamlit para la gestión de Caja, Préstamos, Clientes y Finanzas.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import io
import pandas as pd
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from database import SessionLocal
from prestamo_repository import PrestamoRepository
from cliente_repository import ClienteRepository
from prestamo import EstadoPrestamo, EstadoCuota
from caja_service import CajaService  # Asegúrate de que tu servicio de caja esté disponible

st.set_page_config(
    page_title="Sistema Financiero y de Préstamos",
    page_icon="💰",
    layout="wide"
)

# --- GESTIÓN DE AUTENTICACIÓN SIMPLIFICADA ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = "admin"

def login_screen():
    st.title("🔐 Iniciar Sesión - Sistema Financiero")
    with st.form("login_form"):
        username_input = st.text_input("Usuario", value="admin")
        password_input = st.text_input("Contraseña", type="password")
        submit_login = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

        if submit_login:
            if username_input.strip():
                st.session_state.authenticated = True
                st.session_state.username = username_input.strip().lower()
                st.success(f"¡Bienvenido, {st.session_state.username}!")
                st.rerun()
            else:
                st.error("Por favor, ingresa un usuario válido.")

if not st.session_state.authenticated:
    login_screen()
    st.stop()


# --- MÓDULO 1: DASHBOARD / CAJA ---
def render_dashboard(usuario):
    st.title(f"📊 Dashboard Financiero — {usuario.capitalize()}")
    st.markdown("Resumen general del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()
    try:
        caja_service = CajaService(db, usuario_actual=usuario)
        resumen = caja_service.obtener_resumen_financiero()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(label="💵 Caja Disponible", value=f"${resumen['caja_disponible']:,.2f}")
        with col2:
            st.metric(label="📈 Capital Prestado (Activo)", value=f"${resumen['capital_prestado']:,.2f}")
        with col3:
            st.metric(label="🏦 Capital Total (Caja + Cartera)", value=f"${resumen['capital_total']:,.2f}")

        st.divider()

        # --- SECCIÓN DE NUEVOS MOVIMIENTOS MANUALES (INGRESO GENÉRICO Y REPOSICIÓN - POR DEFECTO: GENÉRICO) ---
        with st.expander("⚙️ Registrar Movimiento de Caja (Ingreso Genérico o Reposición)", expanded=False):
            with st.form("form_ajuste_caja"):
                tipo_movimiento = st.selectbox(
                    "Tipo de Operación *",
                    ["Ingreso Genérico", "Reposición de Capital"]
                )
                monto_movimiento = st.number_input("Monto ($) *", min_value=0.0, value=500.0, step=50.0)
                observacion_movimiento = st.text_input("Observación / Motivo *", placeholder="Ej: Ingreso de efectivo adicional o inyección de capital")
                
                btn_guardar_mov = st.form_submit_button("📥 Registrar Movimiento en Caja", type="primary", use_container_width=True)

                if btn_guardar_mov:
                    if monto_movimiento <= 0:
                        st.warning("El monto debe ser mayor a cero.")
                    elif not observacion_movimiento.strip():
                        st.warning("La observación es obligatoria para este registro.")
                    else:
                        monto_dec = Decimal(str(monto_movimiento))
                        operacion_realizada = False
                        
                        etiqueta_tipo = "REPOSICIÓN DE CAPITAL" if tipo_movimiento == "Reposición de Capital" else "INGRESO GENÉRICO"
                        obs_final = f"[{etiqueta_tipo}] {observacion_movimiento.strip()}"

                        for metodo_caja in ["registrar_ingreso", "registrar_aporte", "registrar_movimiento", "ingresar"]:
                            if hasattr(caja_service, metodo_caja):
                                try:
                                    fn = getattr(caja_service, metodo_caja)
                                    try:
                                        fn(monto=monto_dec, tipo="INGRESO", observacion=obs_final)
                                    except TypeError:
                                        try:
                                            fn(monto=monto_dec, observacion=obs_final)
                                        except TypeError:
                                            fn(monto_dec)
                                    operacion_realizada = True
                                    break
                                except Exception:
                                    pass

                        if not operacion_realizada and hasattr(caja_service, "caja") and caja_service.caja:
                            if hasattr(caja_service.caja, "saldo_disponible"):
                                caja_service.caja.saldo_disponible += monto_dec
                                db.add(caja_service.caja)
                                operacion_realizada = True

                        if operacion_realizada:
                            db.commit()
                            st.success(f"¡{tipo_movimiento} de ${monto_movimiento:,.2f} aplicada con éxito a la caja!")
                            st.rerun()
                        else:
                            db.rollback()
                            st.error("❌ No se pudo registrar el movimiento en el servicio de caja. Revisa los métodos de tu backend.")

        st.divider()

        st.subheader("📜 Últimos Movimientos y Transacciones")
        movimientos = caja_service.listar_movimientos(limite=10)

        if not movimientos:
            st.info("No hay movimientos financieros registrados todavía en este usuario.")
        else:
            data = []
            for m in movimientos:
                data.append({
                    "ID": m.id,
                    "Fecha": getattr(m, "fecha", "N/A"),
                    "Tipo": m.tipo_evento.value if hasattr(m.tipo_evento, "value") else str(m.tipo_evento),
                    "Monto": f"${m.monto:,.2f}" if hasattr(m, "monto") else "$0.00",
                    "Observación": getattr(m, "observacion", "")
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 2: GESTIÓN DE PRÉSTAMOS ---
def generar_pdf_paz_y_salvo(prestamo, cliente, cuotas):
    """
    Genera un archivo PDF en memoria con el certificado oficial de Paz y Salvo del préstamo.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        alignment=1 # Centrado
    )
    
    elements.append(Paragraph("<b>CERTIFICADO DE PAZ Y SALVO</b>", title_style))
    elements.append(Spacer(1, 15))
    
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_solicitud = getattr(prestamo, 'fecha_creacion', None)
    if isinstance(fecha_solicitud, datetime):
        fecha_solicitud_str = fecha_solicitud.strftime("%d/%m/%Y")
    else:
        fecha_solicitud_str = str(fecha_solicitud) if fecha_solicitud else "N/A"

    nombre_cliente = getattr(cliente, 'nombre_completo', 'N/A')

    datos_cliente = f"""
    <b>Nombre del Cliente:</b> {nombre_cliente}<br/>
    <b>Fecha de Emisión del Reporte:</b> {fecha_emision}<br/>
    <b>ID del Préstamo:</b> #{prestamo.id}<br/>
    <b>Fecha de Solicitud del Crédito:</b> {fecha_solicitud_str}<br/>
    <b>Monto Total del Préstamo:</b> ${prestamo.monto_total:,.2f}<br/>
    <b>Saldo Pendiente Actual:</b> <font color="green"><b>Certificado Generado</b></font>
    """
    
    elements.append(Paragraph(datos_cliente, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Historial Detallado de Pagos y Cuotas:</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    tabla_datos = [["Cuota N°", "Valor Cuota", "Monto Abonado", "Estado"]]
    
    if cuotas:
        for c in cuotas:
            estado_val = c.estado.value if hasattr(c.estado, 'value') else str(c.estado)
            tabla_datos.append([
                f"Cuota #{c.numero_cuota}",
                f"${c.monto_cuota:,.2f}",
                f"${c.monto_pagado:,.2f}",
                estado_val
            ])
    else:
        tabla_datos.append(["N/A", "$0.00", "$0.00", "ACTIVO"])
        
    t = Table(tabla_datos, colWidths=[100, 130, 130, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 30))
    
    nota_final = "<i>Este documento certifica oficialmente el estado de la obligación financiera correspondiente a este crédito.</i>"
    elements.append(Paragraph(nota_final, styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def render_prestamos():
    st.title("💳 Gestión de Préstamos")
    
    tab_cartera, tab_nuevo = st.tabs(["📂 Cartera Activa", "➕ Nuevo Préstamo"])

    db = SessionLocal()
    try:
        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)
        usuario_actual = st.session_state.get("username", "admin")

        # --- PESTAÑA 1: CARTERA ACTIVA ---
        with tab_cartera:
            st.subheader("📋 Préstamos en Curso y Finalizados")
            prestamos = prestamo_repo.obtener_por_usuario(usuario_actual)

            if not prestamos:
                st.info("No hay préstamos registrados.")
            else:
                data = []
                prestamos_dict = {}
                
                for p in prestamos:
                    nombre_cliente = getattr(p, "cliente_nombre", None)
                    if not nombre_cliente and hasattr(p, "cliente") and p.cliente:
                        nombre_cliente = getattr(p.cliente, "nombre_completo", "N/A")
                    elif not nombre_cliente:
                        nombre_cliente = "N/A"

                    estado_actual = getattr(p, "estado", EstadoPrestamo.ACTIVO)
                    estado_str = estado_actual.value if hasattr(estado_actual, "value") else str(estado_actual)

                    data.append({
                        "ID": p.id,
                        "Cliente": nombre_cliente,
                        "Capital": f"${p.capital:,.2f}" if hasattr(p, "capital") else "$0.00",
                        "Interés (%)": f"{p.porcentaje_interes}%" if hasattr(p, "porcentaje_interes") else "0%",
                        "Total a Pagar": f"${p.monto_total:,.2f}" if hasattr(p, "monto_total") else "$0.00",
                        "Cuotas": getattr(p, "numero_cuotas", 1),
                        "Estado": estado_str
                    })
                    prestamos_dict[p.id] = p

                df_prestamos = pd.DataFrame(data)
                st.dataframe(df_prestamos, use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("📄 Descarga de Certificado (Paz y Salvo / Reporte)")
                
                prestamo_ids_disponibles = [p.id for p in prestamos]
                if prestamo_ids_disponibles:
                    id_seleccionado = st.selectbox("Seleccione el ID del Préstamo para generar el reporte", options=prestamo_ids_disponibles)
                    prestamo_sel = prestamos_dict.get(id_seleccionado)
                    
                    if prestamo_sel:
                        cuotas_prestamo = getattr(prestamo_sel, "cuotas", [])
                        
                        st.success(f"✅ Préstamo #{prestamo_sel.id} seleccionado correctamente.")
                        
                        pdf_file = generar_pdf_paz_y_salvo(prestamo_sel, prestamo_sel.cliente, cuotas_prestamo)
                        st.download_button(
                            label=f"📥 Descargar Reporte / Paz y Salvo - Préstamo #{prestamo_sel.id} (PDF)",
                            data=pdf_file,
                            file_name=f"Reporte_Prestamo_{prestamo_sel.id}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )

        # --- PESTAÑA 2: NUEVO PRÉSTAMO / DESEMBOLSO ---
        with tab_nuevo:
            st.subheader("Nuevo Desembolso")

            clientes = cliente_repo.obtener_por_usuario(usuario_actual)

            if not clientes:
                st.warning("⚠️ No tienes clientes registrados. Por favor, ve al módulo de 'Clientes' y registra al menos uno antes de otorgar un préstamo.")
                return

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


# --- NAVEGACIÓN PRINCIPAL LATERAL ---
st.sidebar.title("📌 Menú de Navegación")
st.sidebar.markdown(f"Usuario activo: **{st.session_state.username.capitalize()}**")

menu = st.sidebar.radio(
    "Ir a:",
    ["📊 Dashboard / Caja", "💳 Préstamos", "👥 Clientes"]
)

if st.sidebar.button("Cerrar Sesión", type="secondary"):
    st.session_state.authenticated = False
    st.session_state.username = "admin"
    st.rerun()

st.sidebar.divider()


# --- ENRUTADOR DE VISTAS ---
if menu == "📊 Dashboard / Caja":
    render_dashboard(st.session_state.username)
elif menu == "💳 Préstamos":
    render_prestamos()
elif menu == "👥 Clientes":
    st.title("👥 Gestión de Clientes")
    st.info("Módulo de administración de clientes activo.")
