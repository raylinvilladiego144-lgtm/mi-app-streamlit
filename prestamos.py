"""
app/pages/prestamos.py

Vista y controlador para la gestión de préstamos, simulaciones y generación de paz y salvos.
"""

from decimal import Decimal
import io
import streamlit as st

from app.database.database import SessionLocal
from app.repositories.prestamo_repository import PrestamoRepository
from app.repositories.cliente_repository import ClienteRepository

# ReportLab para generación de PDFs
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generar_pdf_paz_y_salvo(cliente_nombre: str, prestamo_id: int) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    elementos = []
    styles = getSampleStyleSheet()
    
    titulo_estilo = ParagraphStyle(
        'TituloPazSalvo',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=1, # Centrado
        textColor=colors.HexColor('#1B365D')
    )
    
    body_estilo = ParagraphStyle(
        'BodyPazSalvo',
        parent=styles['Normal'],
        fontSize=12,
        leading=18,
        alignment=4 # Justificado
    )

    elementos.append(Paragraph("CERTIFICADO DE PAZ Y SALVO", titulo_estilo))
    elementos.append(Spacer(1, 20))
    
    texto_certificacion = f"""
    A quien pueda interesar:<br/><br/>
    Por medio de la presente se certifica que el/la cliente <b>{cliente_nombre}</b> 
    se encuentra a <b>PAZ Y SALVO</b> por todo concepto relacionado con el crédito o 
    préstamo registrado bajo el identificador interno <b>N° {prestamo_id}</b>.<br/><br/>
    El presente documento se expide a solicitud de la parte interesada a los 
    días del mes en curso, habiéndose verificado la cancelación total de los 
    valores adeudados, capital e intereses correspondientes.
    """
    elementos.append(Paragraph(texto_certificacion, body_estilo))
    elementos.append(Spacer(1, 40))
    
    # Tabla de firmas
    firma_data = [
        ["__________________________________", "__________________________________"],
        ["Firma Autorizada / Gerencia", "Recibido Conforme (Cliente)"]
    ]
    tabla_firmas = Table(firma_data, colWidths=[240, 240])
    tabla_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    
    elementos.append(tabla_firmas)
    doc.build(elementos)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def render_prestamos():
    st.markdown("## 💳 Gestión de Préstamos y Cartera")
    st.caption("Control de créditos activos, simulaciones financieras y emisión de paz y salvos")

    db = SessionLocal()

    try:
        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)

        clientes = cliente_repo.listar_todos()
        prestamos_activos = prestamo_repo.listar_activos()

        tab_nuevo, tab_lista, tab_simulador = st.tabs([
            "➕ Nuevo Préstamo", 
            "📋 Préstamos Activos", 
            "🧮 Simulador Financiero"
        ])

        # ==========================================
        # TAB 1: NUEVO PRÉSTAMO
        # ==========================================
        with tab_nuevo:
            st.subheader("Otorgar Nuevo Crédito")
            
            if not clientes:
                st.warning("⚠️ No hay clientes registrados en el sistema. Debe registrar uno antes de crear un préstamo.")
            else:
                # Diccionario seguro con formato id para evitar colisiones por nombres duplicados
                clientes_dict = {f"{c.nombre_completo} (ID: {c.id})": c for c in clientes if hasattr(c, "nombre_completo")}
                
                with st.form("form_nuevo_prestamo", clear_on_submit=True):
                    cliente_seleccionado_str = st.selectbox("Seleccionar Cliente *", options=list(clientes_dict.keys()))
                    
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        capital = st.number_input("Capital a Prestar ($) *", min_value=10.0, step=100.0, format="%.2f")
                    with col_p2:
                        tasa_interes = st.number_input("Tasa de Interés (%) *", min_value=0.0, step=0.5, format="%.2f")
                        
                    plazo_dias = st.number_input("Plazo en Días *", min_value=1, step=1, value=30)
                    observacion = st.text_area("Observaciones o Destino del Préstamo", placeholder="Ej. Capital de trabajo para mercancía")
                    
                    btn_crear = st.form_submit_button("Crear Préstamo", type="primary", use_container_width=True)
                    
                    if btn_crear:
                        cliente_obj = clientes_dict[cliente_seleccionado_str]
                        try:
                            prestamo_repo.crear_prestamo(
                                cliente_id=cliente_obj.id,
                                capital=Decimal(str(capital)),
                                tasa_interes=Decimal(str(tasa_interes)),
                                plazo_dias=int(plazo_dias),
                                observacion=observacion
                            )
                            st.success("🎉 ¡Préstamo creado con éxito!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ Error al crear el préstamo: {ex}")

        # ==========================================
        # TAB 2: PRÉSTAMOS ACTIVOS
        # ==========================================
        with tab_lista:
            st.subheader("Listado de Préstamos Vigentes")
            
            if not prestamos_activos:
                st.info("ℹ️ No hay préstamos activos en este momento.")
            else:
                for p in prestamos_activos:
                    with st.expander(f"Préstamo #{getattr(p, 'id', 'N/A')} - Cliente ID: {getattr(p, 'cliente_id', 'N/A')}"):
                        c_info1, c_info2 = st.columns(2)
                        with c_info1:
                            st.write(f"**Capital Inicial:** ${getattr(p, 'capital', 0.0):,.2f}")
                            st.write(f"**Tasa de Interés:** {getattr(p, 'tasa_interes', 0.0)}%")
                        with c_info2:
                            st.write(f"**Plazo:** {getattr(p, 'plazo_dias', 0)} días")
                            st.write(f"Estado: **{getattr(p, 'estado', 'ACTIVO')}**")
                            
                        # Botón para descargar Paz y Salvo si el crédito está pagado o se requiere
                        if st.button(f"Generar Paz y Salvo (Préstamo #{p.id})", key=f"pdf_{p.id}"):
                            # Buscar nombre de cliente asociado de forma segura
                            nombre_cli = "Cliente General"
                            for c in clientes:
                                if c.id == p.cliente_id:
                                    nombre_cli = c.nombre_completo
                                    break
                                    
                            pdf_data = generar_pdf_paz_y_salvo(nombre_cli, p.id)
                            st.download_button(
                                label="📥 Descargar PDF de Paz y Salvo",
                                data=pdf_data,
                                file_name=f"paz_y_salvo_prestamo_{p.id}.pdf",
                                mime="application/pdf",
                                key=f"download_{p.id}"
                            )

        # ==========================================
        # TAB 3: SIMULADOR FINANCIERO
        # ==========================================
        with tab_simulador:
            st.subheader("Simulador de Créditos")
            
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                cap_sim_input = st.number_input("Capital a simular ($)", min_value=10.0, value=1000.0, step=100.0)
                tasa_sim_input = st.number_input("Tasa estimada (%)", min_value=0.0, value=10.0, step=0.5)
            with s_col2:
                plazo_sim_input = st.number_input("Plazo en días", min_value=1, value=30, step=1)
                
            cap_sim = Decimal(str(cap_sim_input))
            tasa_sim = Decimal(str(tasa_sim_input)) / Decimal("100")
            total_cobrar_sim = cap_sim + (cap_sim * tasa_sim)
            cuota_diaria_sim = total_cobrar_sim / Decimal(str(plazo_sim_input)) if plazo_sim_input > 0 else 0

            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Interés Proyectado", f"${(cap_sim * tasa_sim):,.2f}")
            m2.metric("Total a Cobrar", f"${total_cobrar_sim:,.2f}")
            m3.metric("Cuota Referencial Diaria", f"${cuota_diaria_sim:,.2f}")

    finally:
        db.close()
