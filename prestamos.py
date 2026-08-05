"""
prestamos.py

Vista y controlador para la gestión de préstamos, simulaciones, generación de paz y salvos,
visualización de cuotas y motor de abonos inteligentes.
"""

from decimal import Decimal
from datetime import date
import io
import streamlit as st

# Importaciones planas para la estructura de tu proyecto
from database import SessionLocal
from prestamo_repository import PrestamoRepository
from cliente_repository import ClienteRepository
from app.models.prestamo import Cuota, EstadoCuota, EstadoPrestamo

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
        alignment=1,  # Centrado
        textColor=colors.HexColor('#1B365D')
    )
    
    body_estilo = ParagraphStyle(
        'BodyPazSalvo',
        parent=styles['Normal'],
        fontSize=12,
        leading=18,
        alignment=4  # Justificado
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


def render_prestamos(usuario_actual: str = "admin"):
    # Normalización limpia de usuario para respetar sesiones
    current_user = str(usuario_actual or "admin").strip().lower()

    st.markdown("## 💳 Gestión de Préstamos y Cartera")
    st.caption("Control de créditos activos, visualización de cuotas, simulaciones financieras y emisión de paz y salvos")

    db = SessionLocal()

    try:
        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)

        # Listar respetando la sesión actual del usuario o administrador
        clientes = cliente_repo.listar_todos()
        prestamos_activos = prestamo_repo.obtener_por_usuario(current_user) if current_user != "admin" else prestamo_repo.listar_activos()

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
                clientes_dict = {f"{c.nombre_completo} (ID: {c.id})": c for c in clientes if hasattr(c, "nombre_completo")}
                
                with st.form("form_nuevo_prestamo", clear_on_submit=True):
                    cliente_seleccionado_str = st.selectbox("Seleccionar Cliente *", options=list(clientes_dict.keys()))
                    
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        capital = st.number_input("Capital a Prestar ($) *", min_value=10.0, step=100.0, format="%.2f")
                        tasa_interes = st.number_input("Tasa de Interés (%) *", min_value=0.0, step=0.5, format="%.2f")
                    with col_p2:
                        numero_cuotas = st.number_input("Número de Cuotas *", min_value=1, step=1, value=1)
                        plazo_dias = st.number_input("Plazo Total en Días *", min_value=1, step=1, value=30)
                        
                    observacion = st.text_area("Observaciones o Destino del Préstamo", placeholder="Ej. Capital de trabajo para mercancía")
                    
                    btn_crear = st.form_submit_button("Crear Préstamo", type="primary", use_container_width=True)
                    
                    if btn_crear:
                        cliente_obj = clientes_dict[cliente_seleccionado_str]
                        try:
                            # Pasamos explícitamente el usuario actual para ligar la caja y el crédito
                            prestamo_repo.crear_prestamo(
                                cliente_id=cliente_obj.id,
                                capital=Decimal(str(capital)),
                                tasa_interes=Decimal(str(tasa_interes)),
                                num_cuotas=int(numero_cuotas),
                                plazo_dias=int(plazo_dias),
                                observaciones=observacion,
                                usuario=current_user
                            )
                            st.success("🎉 ¡Préstamo creado con éxito y registrado en caja!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ Error al crear el préstamo: {ex}")

        # ==========================================
        # TAB 2: PRÉSTAMOS ACTIVOS Y CUOTAS (CON MOTOR DE ABONOS)
        # ==========================================
        with tab_lista:
            st.subheader("Listado de Préstamos Vigentes y Cuotas")
            
            if not prestamos_activos:
                st.info("ℹ️ No hay préstamos activos registrados para este usuario.")
            else:
                for p in prestamos_activos:
                    nombre_cli = "Cliente General"
                    for c in clientes:
                        if c.id == p.cliente_id:
                            nombre_cli = c.nombre_completo
                            break

                    with st.expander(f"Préstamo #{getattr(p, 'id', 'N/A')} — {nombre_cli} | Capital: ${getattr(p, 'capital', 0.0):,.2f}"):
                        c_info1, c_info2 = st.columns(2)
                        with c_info1:
                            st.write(f"**Capital Inicial:** ${getattr(p, 'capital', 0.0):,.2f}")
                            tasa_val = getattr(p, 'porcentaje_interes', None) if getattr(p, 'porcentaje_interes', None) is not None else getattr(p, 'tasa_interes', 0.0)
                            st.write(f"**Tasa de Interés:** {tasa_val}%")
                        with c_info2:
                            plazo_val = getattr(p, 'numero_cuotas', None) if getattr(p, 'numero_cuotas', None) is not None else getattr(p, 'plazo_dias', 0)
                            st.write(f"**Plazo / Cuotas:** {plazo_val}")
                            estado_val = getattr(p, 'estado', 'ACTIVO')
                            estado_str = estado_val.value if hasattr(estado_val, 'value') else str(estado_val)
                            st.write(f"Estado: **{estado_str}**")

                        st.markdown("---")
                        st.markdown("### 📊 Tabla de Cuotas y Control de Saldo")

                        # Obtener cuotas asociadas al préstamo actual ordenadas por número de cuota
                        cuotas_prestamo = db.query(Cuota).filter(Cuota.prestamo_id == p.id).order_by(Cuota.numero_cuota).all()

                        if not cuotas_prestamo:
                            st.warning("⚠️ Este préstamo no tiene cuotas generadas en el sistema.")
                        else:
                            # Renderizar tabla visual de cuotas
                            datos_cuotas = []
                            for cuota in cuotas_prestamo:
                                saldo_pend = cuota.monto_cuota - cuota.monto_pagado
                                estado_cuota_str = cuota.estado.value if hasattr(cuota.estado, 'value') else str(cuota.estado)
                                datos_cuotas.append({
                                    "N° Cuota": cuota.numero_cuota,
                                    "Monto Cuota ($)": float(cuota.monto_cuota),
                                    "Pagado ($)": float(cuota.monto_pagado),
                                    "Saldo Pendiente ($)": float(saldo_pend),
                                    "Vencimiento": str(cuota.fecha_pago_esperada),
                                    "Estado": estado_cuota_str
                                })
                            
                            st.dataframe(datos_cuotas, use_container_width=True)

                            # 💡 Formulario de entrada de abono con segmentación inteligente
                            st.markdown("#### 💰 Registrar Abono / Pago Inteligente")
                            st.caption("El sistema distribuirá automáticamente el abono cubriendo las cuotas pendientes en orden cronológico.")

                            with st.form(key=f"form_abono_{p.id}"):
                                col_val, col_btn = st.columns([2, 1])
                                with col_val:
                                    valor_abono = st.number_input(
                                        f"Valor del Abono ($) [Préstamo #{p.id}]",
                                        min_value=1.0,
                                        step=10.0,
                                        format="%.2f",
                                        key=f"input_abono_{p.id}"
                                    )
                                with col_btn:
                                    st.text("") # Espaciador
                                    st.text("")
                                    btn_procesar = st.form_submit_button("Aplicar Abono", type="primary", use_container_width=True)

                                if btn_procesar:
                                    monto_restante = Decimal(str(valor_abono))
                                    
                                    # Motor inteligente de distribución de pagos por cuota
                                    for cuota in cuotas_prestamo:
                                        if monto_restante <= 0:
                                            break
                                        
                                        saldo_pendiente = cuota.monto_cuota - cuota.monto_pagado
                                        if saldo_pendiente <= 0:
                                            continue  # Cuota ya pagada
                                        
                                        if monto_restante >= saldo_pendiente:
                                            monto_restante -= saldo_pendiente
                                            cuota.monto_pagado = cuota.monto_cuota
                                            cuota.estado = EstadoCuota.PAGADA
                                            cuota.fecha_pago_real = date.today()
                                        else:
                                            cuota.monto_pagado += monto_restante
                                            cuota.estado = EstadoCuota.PARCIAL
                                            cuota.fecha_pago_real = date.today()
                                            monto_restante = Decimal("0.00")

                                    db.commit()

                                    # Validar si todas las cuotas quedaron pagadas para liquidar el préstamo automáticamente
                                    cuotas_verificacion = db.query(Cuota).filter(Cuota.prestamo_id == p.id).all()
                                    if all(c.estado == EstadoCuota.PAGADA for c in cuotas_verificacion):
                                        p.estado = EstadoPrestamo.LIQUIDADO
                                        db.commit()
                                        st.success(f"🎯 ¡Todas las cuotas cubiertas! El Préstamo #{p.id} ha sido marcado como **LIQUIDADO**.")
                                    else:
                                        st.success("✅ Abono aplicado e integrado correctamente sobre las cuotas pendientes.")
                                    
                                    st.rerun()

                        st.divider()

                        # Botón persistente para descargar Paz y Salvo
                        pdf_data = generar_pdf_paz_y_salvo(nombre_cli, p.id)
                        st.download_button(
                            label=f"📥 Descargar PDF de Paz y Salvo (Préstamo #{p.id})",
                            data=pdf_data,
                            file_name=f"paz_y_salvo_prestamo_{p.id}.pdf",
                            mime="application/pdf",
                            key=f"download_{p.id}",
                            use_container_width=True
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
