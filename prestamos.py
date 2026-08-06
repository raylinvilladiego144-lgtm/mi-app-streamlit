"""
prestamos.py

Vista y controlador para la gestión de préstamos, simulaciones, generación de paz y salvos,
visualización de cuotas y motor de abonos inteligentes.
"""

from decimal import Decimal
from datetime import date
import io
import streamlit as st

# Importaciones planas corregidas para la estructura de tu proyecto
from database import SessionLocal
from prestamo_repository import PrestamoRepository
from cliente_repository import ClienteRepository
from prestamo import Cuota, EstadoCuota, EstadoPrestamo, ModalidadInteres
from evento import EventoFinanciero, TipoEvento
from prestamo_service import PrestamoService

# ReportLab para generación de PDFs
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generar_pdf_paz_y_salvo(cliente_nombre: str, cliente_documento: str, prestamo_id: int, capital: float, interes: float, monto_total: float, fecha_inicio: str, fecha_vencimiento: str, cuotas_data: list, estado: str) -> bytes:
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
        fontSize=18,
        alignment=1,  # Centrado
        textColor=colors.HexColor('#1B365D')
    )
    
    body_estilo = ParagraphStyle(
        'BodyPazSalvo',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        alignment=4  # Justificado
    )

    elementos.append(Paragraph("CERTIFICADO DE PAZ Y SALVO", titulo_estilo))
    elementos.append(Spacer(1, 15))
    
    texto_certificacion = f"""
    A quien pueda interesar:<br/><br/>
    Por medio de la presente se certifica que el/la cliente <b>{cliente_nombre}</b>, identificado(a) con documento N° <b>{cliente_documento}</b>, 
    se encuentra a <b>PAZ Y SALVO</b> por todo concepto relacionado con el crédito o préstamo registrado bajo el identificador interno <b>N° {prestamo_id}</b>.<br/><br/>
    Detalles del crédito liquidado:<br/>
    - <b>Capital:</b> ${capital:,.2f}<br/>
    - <b>Interés:</b> ${interes:,.2f}<br/>
    - <b>Monto Total:</b> ${monto_total:,.2f}<br/>
    - <b>Fecha de Inicio:</b> {fecha_inicio}<br/>
    - <b>Fecha de Vencimiento:</b> {fecha_vencimiento}<br/>
    - <b>Estado Actual:</b> {estado}<br/><br/>
    El presente documento se expide a solicitud de la parte interesada a los días del mes en curso, habiéndose verificado la cancelación total de los valores adeudados.
    """
    elementos.append(Paragraph(texto_certificacion, body_estilo))
    elementos.append(Spacer(1, 15))

    elementos.append(Paragraph("<b>Resumen de Cuotas Pagadas:</b>", styles['Heading3']))
    elementos.append(Spacer(1, 5))

    # Tabla de cuotas para el PDF
    tabla_cuotas_data = [["N° Cuota", "Monto", "Pagado", "Vesperada", "V. Real", "Estado"]]
    for c in cuotas_data:
        tabla_cuotas_data.append([
            str(c.numero_cuota),
            f"${float(c.monto_cuota):,.2f}",
            f"${float(c.monto_pagado):,.2f}",
            str(c.fecha_pago_esperada),
            str(c.fecha_pago_real or "N/A"),
            str(c.estado.value if hasattr(c.estado, 'value') else c.estado)
        ])
    
    t_cuotas = Table(tabla_cuotas_data, colWidths=[60, 90, 90, 90, 90, 90])
    t_cuotas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elementos.append(t_cuotas)
    elementos.append(Spacer(1, 30))
    
    # Tabla de firmas
    firma_data = [
        ["__________________________________", "__________________________________"],
        ["Firma Autorizada / Gerencia", f"Firma / Recibido Conforme ({cliente_nombre})"]
    ]
    tabla_firmas = Table(firma_data, colWidths=[250, 250])
    tabla_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    
    elementos.append(tabla_firmas)
    doc.build(elementos)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def render_prestamos(usuario_actual: str = "admin"):
    current_user = str(usuario_actual or "admin").strip().lower()

    st.markdown("## 💳 Gestión de Préstamos y Cartera")
    st.caption("Control de créditos activos, visualización de cuotas, simulaciones financieras, refinanciación y emisión de paz y salvos")

    db = SessionLocal()

    try:
        # ⚡ Limpieza de sesión pendiente para evitar PendingRollbackError tras errores previos
        try:
            db.rollback()
        except Exception:
            pass

        prestamo_repo = PrestamoRepository(db)
        cliente_repo = ClienteRepository(db)
        prestamo_service = PrestamoService(db)

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
                
                with st.form("form_nuevo_prestamo_unico", clear_on_submit=True):
                    cliente_seleccionado_str = st.selectbox("Seleccionar Cliente *", options=list(clientes_dict.keys()), key="sel_cli_nuevo_prestamo")
                    
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        capital = st.number_input("Capital a Prestar ($) *", min_value=10.0, step=100.0, format="%.2f", key="input_cap_nuevo")
                        tasa_interes = st.number_input("Tasa de Interés (%) *", min_value=0.0, step=0.5, format="%.2f", key="input_tasa_nuevo")
                    with col_p2:
                        numero_cuotas = st.number_input("Número de Cuotas *", min_value=1, step=1, value=1, key="input_cuotas_nuevo")
                        plazo_dias = st.number_input("Plazo Total en Días *", min_value=1, step=1, value=30, key="input_plazo_nuevo")
                        
                    observacion = st.text_area("Observaciones o Destino del Préstamo", placeholder="Ej. Capital de trabajo para mercancía", key="input_obs_nuevo")
                    
                    btn_crear = st.form_submit_button("Crear Préstamo", type="primary", use_container_width=True)
                    
                    if btn_crear:
                        cliente_obj = clientes_dict[cliente_seleccionado_str]
                        try:
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
                            db.rollback()
                            st.error(f"❌ Error al crear el préstamo: {ex}")

        # ==========================================
        # TAB 2: PRÉSTAMOS ACTIVOS Y CUOTAS (CON MOTOR DE ABONOS)
        # ==========================================
        with tab_lista:
            st.subheader("Listado de Préstamos Vigentes y Cuotas")
            
            if not prestamos_activos:
                st.info("ℹ️ No hay préstamos vigentes registrados para este usuario.")
            else:
                for p in prestamos_activos:
                    nombre_cli = "Cliente General"
                    doc_cli = "N/A"
                    for c in clientes:
                        if c.id == p.cliente_id:
                            nombre_cli = c.nombre_completo
                            doc_cli = getattr(c, 'documento', 'N/A')
                            break

                    estado_val = getattr(p, 'estado', 'ACTIVO')
                    estado_str = estado_val.value if hasattr(estado_val, 'value') else str(estado_val)

                    with st.expander(f"Préstamo #{getattr(p, 'id', 'N/A')} — {nombre_cli} | Capital: ${getattr(p, 'capital', 0.0):,.2f} | Estado: {estado_str}"):
                        
                        c_info1, c_info2, c_info3 = st.columns(3)
                        with c_info1:
                            st.write(f"**Capital:** ${getattr(p, 'capital', 0.0):,.2f}")
                            tasa_val = getattr(p, 'porcentaje_interes', None) if getattr(p, 'porcentaje_interes', None) is not None else getattr(p, 'tasa_interes', 0.0)
                            st.write(f"**Interés:** {tasa_val}%")
                            st.write(f"**Monto Total:** ${getattr(p, 'monto_total', 0.0):,.2f}")
                        with c_info2:
                            st.write(f"**Fecha Adquisición:** {getattr(p, 'fecha_inicio', 'N/A')}")
                            st.write(f"**Fecha Vencimiento:** {getattr(p, 'fecha_vencimiento', 'N/A')}")
                            st.write(f"**Número de Cuotas:** {getattr(p, 'numero_cuotas', 'N/A')}")
                        with c_info3:
                            st.write(f"**Saldo Pendiente:** ${getattr(p, 'saldo_pendiente', 0.0):,.2f}")
                            st.write(f"**N° Refinanciaciones:** {getattr(p, 'numero_refinanciaciones', 0)}")
                            st.write(f"Estado: **{estado_str}**")

                        st.markdown("---")
                        st.markdown("### 📊 Tabla de Cuotas")

                        cuotas_prestamo = db.query(Cuota).filter(Cuota.prestamo_id == p.id).order_by(Cuota.numero_cuota).all()

                        if not cuotas_prestamo:
                            st.warning("⚠️ Este préstamo no tiene cuotas generadas en el sistema.")
                        else:
                            datos_cuotas = []
                            for cuota in cuotas_prestamo:
                                saldo_c = getattr(cuota, 'saldo_cuota', cuota.monto_cuota - cuota.monto_pagado)
                                estado_cuota_str = cuota.estado.value if hasattr(cuota.estado, 'value') else str(cuota.estado)
                                datos_cuotas.append({
                                    "Número": cuota.numero_cuota,
                                    "Monto ($)": float(cuota.monto_cuota),
                                    "Pagado ($)": float(cuota.monto_pagado),
                                    "Saldo Cuota ($)": float(saldo_c),
                                    "Fecha esperada": str(cuota.fecha_pago_esperada),
                                    "Fecha real de pago": str(cuota.fecha_pago_real or "Pendiente"),
                                    "Estado": estado_cuota_str
                                })
                            
                            st.dataframe(datos_cuotas, use_container_width=True)

                            st.markdown("#### 💰 Pago Inteligente")
                            st.caption("Distribución automática cubriendo cuotas pendientes en orden cronológico.")

                            with st.form(key=f"form_pago_inteligente_{p.id}"):
                                valor_abono = st.number_input(
                                    f"Valor del Abono ($) [Préstamo #{p.id}]",
                                    min_value=1.0,
                                    step=10.0,
                                    format="%.2f",
                                    key=f"input_pago_inteligente_{p.id}"
                                )
                                btn_procesar_pago = st.form_submit_button("Aplicar Pago Inteligente", type="primary", use_container_width=True)

                                if btn_procesar_pago:
                                    try:
                                        prestamo_service.registrar_pago_inteligente(
                                            prestamo_id=p.id,
                                            monto_pagado=Decimal(str(valor_abono)),
                                            usuario_actual=current_user  # ⚡ Corregido a usuario_actual
                                        )
                                        st.success("✅ Pago inteligente aplicado y registrado correctamente.")
                                        st.rerun()
                                    except Exception as err:
                                        db.rollback()
                                        st.error(f"❌ Error al procesar el pago: {err}")

                        st.divider()

                        st.markdown("#### 🔄 Refinanciación de Préstamo")
                        with st.form(key=f"form_refinanciacion_{p.id}"):
                            desea_refinanciar = st.selectbox("¿Desea refinanciar?", options=["No", "Sí"], key=f"sel_refinanciar_{p.id}")
                            
                            nuevo_capital_ref = st.number_input("Nuevo Capital / Saldo Base ($)", min_value=0.0, value=float(getattr(p, 'capital', 0.0)), step=100.0, key=f"ref_capital_{p.id}")
                            nueva_tasa = st.number_input("Nueva tasa (%)", min_value=0.0, value=float(tasa_val), step=0.5, key=f"ref_tasa_{p.id}")
                            nuevo_plazo = st.number_input("Nuevo plazo en días", min_value=1, value=30, step=1, key=f"ref_plazo_{p.id}")
                            nuevo_plazo_cuotas = st.number_input("Nuevo Número de Cuotas", min_value=1, value=int(getattr(p, 'numero_cuotas', 1)), step=1, key=f"ref_num_cuotas_{p.id}")
                            nueva_fecha = st.date_input("Nueva fecha de vencimiento", value=date.today(), key=f"ref_fecha_{p.id}")
                            observacion_ref = st.text_area("Observación de refinanciación", key=f"ref_obs_{p.id}")
                            
                            btn_refinanciar = st.form_submit_button("Procesar Refinanciación", use_container_width=True)

                            if btn_refinanciar:
                                if desea_refinanciar == "Sí":
                                    try:
                                        prestamo_service.refinanciar_prestamo(
                                            prestamo_id=p.id,
                                            nuevo_capital=Decimal(str(nuevo_capital_ref)),
                                            nueva_tasa=Decimal(str(nueva_tasa)),
                                            nuevo_plazo=int(nuevo_plazo_cuotas),
                                            nueva_fecha_vencimiento=nueva_fecha,
                                            observacion=observacion_ref,
                                            usuario=current_user
                                        )
                                        st.success("🎉 Préstamo refinanciado con éxito.")
                                        st.rerun()
                                    except Exception as ex_ref:
                                        db.rollback()
                                        st.error(f"❌ Error al refinanciar: {ex_ref}")
                                else:
                                    st.info("ℹ️ Seleccione 'Sí' para proceder con la refinanciación.")

                        st.divider()

                        st.markdown("#### 📜 Historial del Préstamo")
                        eventos_prestamo = db.query(EventoFinanciero).filter(EventoFinanciero.prestamo_id == p.id).all()
                        if not eventos_prestamo:
                            st.info("ℹ️ No hay eventos financieros registrados para este préstamo.")
                        else:
                            datos_eventos = []
                            for ev in eventos_prestamo:
                                datos_eventos.append({
                                    "Fecha": str(getattr(ev, 'fecha', getattr(ev, 'creado_en', ''))),
                                    "Tipo": getattr(ev, 'tipo_evento', getattr(ev, 'tipo', 'TRANSACCIÓN')),
                                    "Monto ($)": float(getattr(ev, 'monto', 0.0)),
                                    "Usuario": getattr(ev, 'usuario', current_user),
                                    "Observación": getattr(ev, 'observacion', '')
                                })
                            st.dataframe(datos_eventos, use_container_width=True)

                        st.divider()

                        if estado_val == EstadoPrestamo.LIQUIDADO or estado_str.upper() == "LIQUIDADO":
                            st.success("🎯 Este crédito se encuentra **LIQUIDADO**. Puede descargar su Paz y Salvo:")
                            pdf_data = generar_pdf_paz_y_salvo(
                                cliente_nombre=nombre_cli,
                                cliente_documento=doc_cli,
                                prestamo_id=p.id,
                                capital=float(getattr(p, 'capital', 0.0)),
                                interes=float(getattr(p, 'monto_total', 0.0) - getattr(p, 'capital', 0.0)),
                                monto_total=float(getattr(p, 'monto_total', 0.0)),
                                fecha_inicio=str(getattr(p, 'fecha_inicio', '')),
                                fecha_vencimiento=str(getattr(p, 'fecha_vencimiento', '')),
                                cuotas_data=cuotas_prestamo,
                                estado=estado_str
                            )
                            st.download_button(
                                label=f"📥 Descargar PDF de Paz y Salvo (Préstamo #{p.id})",
                                data=pdf_data,
                                file_name=f"paz_y_salvo_prestamo_{p.id}.pdf",
                                mime="application/pdf",
                                key=f"download_paz_salvo_{p.id}",
                                use_container_width=True
                            )
                        else:
                            st.info("ℹ️ El certificado de Paz y Salvo estará disponible una vez el préstamo sea totalmente liquidado.")

        # ==========================================
        # TAB 3: SIMULADOR FINANCIERO
        # ==========================================
        with tab_simulador:
            st.subheader("Simulador de Créditos")
            
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                cap_sim_input = st.number_input("Capital a simular ($)", min_value=10.0, value=1000.0, step=100.0, key="sim_cap_input")
                tasa_sim_input = st.number_input("Tasa estimada (%)", min_value=0.0, value=10.0, step=0.5, key="sim_tasa_input")
            with s_col2:
                plazo_sim_input = st.number_input("Plazo en días", min_value=1, value=30, step=1, key="sim_plazo_input")
                
            cap_sim = Decimal(str(cap_sim_input))
            tasa_sim = Decimal(str(tasa_sim_input)) / Decimal("100")
            total_cobrar_sim = cap_sim + (cap_sim * tasa_sim)
            cuota_diaria_sim = total_cobrar_sim / Decimal(str(plazo_sim_input)) if plazo_sim_input > 0 else 0

            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Interés Proyectado", f"${(cap_sim * tasa_sim):,.2f}")
            m2.metric("Total a Cobrar", f"${total_cobrar_sim:,.2f}")
            m3.metric("Cuota Referencial Diaria", f"${cuota_diaria_sim:,.2f}")

    except Exception as e:
        db.rollback()
        st.error(f"❌ Ocurrió un error en el módulo de préstamos: {e}")
    finally:
        db.close()
