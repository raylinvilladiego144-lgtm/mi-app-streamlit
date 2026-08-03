"""
prestamos.py
Módulo de gestión de préstamos, cartera activa, creación de nuevos desembolsos y generación de Paz y Salvo.
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
    <b>Saldo Pendiente Actual:</b> <font color="green"><b>$0.00 (PAZ Y SALVO)</b></font>
    """
    
    elements.append(Paragraph(datos_cliente, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Historial Detallado de Pagos y Cuotas:</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    tabla_datos = [["Cuota N°", "Valor Cuota", "Monto Abonado", "Estado"]]
    
    for c in cuotas:
        estado_val = c.estado.value if hasattr(c.estado, 'value') else str(c.estado)
        tabla_datos.append([
            f"Cuota #{c.numero_cuota}",
            f"${c.monto_cuota:,.2f}",
            f"${c.monto_pagado:,.2f}",
            estado_val
        ])
        
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
    
    nota_final = "<i>Este documento certifica oficialmente que el cliente ha cancelado la totalidad de la obligación financiera correspondiente a este crédito.</i>"
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
                st.subheader("📄 Descarga de Certificado de Paz y Salvo")
                
                # Selector para descargar el paz y salvo de cualquier préstamo completado
                prestamo_ids_disponibles = [p.id for p in prestamos]
                if prestamo_ids_disponibles:
                    id_seleccionado = st.selectbox("Seleccione el ID del Préstamo para verificar/descargar Paz y Salvo", options=prestamo_ids_disponibles)
                    prestamo_sel = prestamos_dict.get(id_seleccionado)
                    
                    if prestamo_sel:
                        # Verificar si todas las cuotas están pagadas
                        cuotas_prestamo = getattr(prestamo_sel, "cuotas", [])
                        todas_pagadas = all(
                            (c.estado == EstadoCuota.PAGADA or c.monto_pagado >= c.monto_cuota) 
                            for c in cuotas_prestamo
                        ) if cuotas_prestamo else False

                        if todas_pagadas or prestamo_sel.estado == EstadoPrestamo.PAGADO:
                            st.success(f"✅ El Préstamo #{prestamo_sel.id} se encuentra a Paz y Salvo.")
                            
                            pdf_file = generar_pdf_paz_y_salvo(prestamo_sel, prestamo_sel.cliente, cuotas_prestamo)
                            st.download_button(
                                label=f"📥 Descargar Paz y Salvo - Préstamo #{prestamo_sel.id} (PDF)",
                                data=pdf_file,
                                file_name=f"Paz_y_Salvo_Prestamo_{prestamo_sel.id}.pdf",
                                mime="application/pdf",
                                type="primary"
                            )
                        else:
                            st.info(f"ℹ️ El Préstamo #{prestamo_sel.id} aún tiene cuotas pendientes o saldo por cobrar. El certificado estará disponible al finalizarlo.")

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
