import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generar_pdf_paz_y_salvo(prestamo, cliente, cuotas) -> io.BytesIO:
    """
    Genera un archivo PDF en memoria con el certificado de Paz y Salvo del préstamo.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Estilo de título
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        alignment=1 # Centrado
    )
    
    # Encabezado del documento
    elements.append(Paragraph("<b>CERTIFICADO DE PAZ Y SALVO</b>", title_style))
    elements.append(Spacer(1, 15))
    
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_solicitud = getattr(prestamo, 'fecha_creacion', getattr(prestamo, 'fecha_inicio', None))
    
    if isinstance(fecha_solicitud, datetime) or hasattr(fecha_solicitud, 'strftime'):
        fecha_solicitud_str = fecha_solicitud.strftime("%d/%m/%Y")
    else:
        fecha_solicitud_str = str(fecha_solicitud) if fecha_solicitud else "N/A"

    nombre_cliente = getattr(cliente, 'nombre_completo', 'N/A')
    documento_cliente = getattr(cliente, 'documento', 'N/A')

    # Datos del Préstamo
    datos_cliente = f"""
    <b>Nombre del Cliente:</b> {nombre_cliente}<br/>
    <b>Documento:</b> {documento_cliente}<br/>
    <b>Fecha de Emisión del Reporte:</b> {fecha_emision}<br/>
    <br/>
    <b>ID del Préstamo:</b> #{prestamo.id}<br/>
    <b>Fecha de Solicitud del Crédito:</b> {fecha_solicitud_str}<br/>
    <b>Monto Total del Préstamo:</b> ${prestamo.monto_total:,.2f}<br/>
    <b>Saldo Pendiente Actual:</b> <font color="green"><b>$0.00 (PAZ Y SALVO)</b></font>
    """
    
    elements.append(Paragraph(datos_cliente, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Historial de Fechas y Pagos de Cuotas
    elements.append(Paragraph("<b>Historial Detallado de Pagos y Cuotas:</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Cabecera de la tabla
    tabla_datos = [["Cuota N°", "Valor Cuota", "Monto Abonado", "Estado", "Fecha de Pago"]]
    
    # Ordenar cuotas para el reporte
    cuotas_ordenadas = sorted(cuotas, key=lambda x: getattr(x, 'numero_cuota', 0))
    
    for c in cuotas_ordenadas:
        estado_val = c.estado.value if hasattr(c.estado, 'value') else str(c.estado)
        monto_pagado = getattr(c, 'monto_pagado', 0.0) or 0.0
        fecha_pago = getattr(c, 'fecha_pago_real', 'N/A')
        if hasattr(fecha_pago, 'strftime'):
            fecha_pago = fecha_pago.strftime("%d/%m/%Y")
            
        tabla_datos.append([
            f"Cuota #{c.numero_cuota}",
            f"${c.monto_cuota:,.2f}",
            f"${monto_pagado:,.2f}",
            estado_val,
            str(fecha_pago)
        ])
        
    t = Table(tabla_datos, colWidths=[70, 110, 110, 90, 100])
    
    # Estilo base de la tabla
    estilo_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]
    
    # Efecto cebra para las filas de datos
    for i in range(1, len(tabla_datos)):
        bg_color = colors.HexColor('#F8FAFC') if i % 2 == 0 else colors.white
        estilo_tabla.append(('BACKGROUND', (0, i), (-1, i), bg_color))
        
    t.setStyle(TableStyle(estilo_tabla))
    
    elements.append(t)
    elements.append(Spacer(1, 30))
    
    # Nota Final
    nota_final = """
    <i>Este documento certifica oficialmente que el cliente ha cancelado la totalidad 
    de la obligación financiera correspondiente a este crédito a satisfacción.</i>
    """
    elements.append(Paragraph(nota_final, styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
