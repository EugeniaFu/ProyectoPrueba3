import os
from io import BytesIO
from datetime import datetime
from flask import Blueprint, redirect, request, jsonify, send_file, current_app, url_for
from utils.db import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
from num2words import num2words 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


prefactura_bp = Blueprint('prefactura', __name__, url_prefix='/prefactura')

# === Endpoint: Obtener datos de prefactura (AJAX) ===
@prefactura_bp.route('/<int:renta_id>')
def obtener_prefactura(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Detalle de productos
    cursor.execute("""
        SELECT p.nombre, d.cantidad, d.dias_renta, d.costo_unitario, d.subtotal
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
        WHERE d.renta_id = %s
    """, (renta_id,))
    detalle = cursor.fetchall()
    # Totales y traslado
    cursor.execute("""
        SELECT total_con_iva, traslado, costo_traslado
        FROM rentas
        WHERE id = %s
    """, (renta_id,))
    total_info = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "detalle": detalle,
        "total_con_iva": total_info['total_con_iva'] if total_info else 0,
        "traslado": total_info['traslado'] if total_info else None,
        "costo_traslado": total_info['costo_traslado'] if total_info else 0
    })








# === Endpoint: Registrar pago 
@prefactura_bp.route('/pago/<int:renta_id>', methods=['POST'])
def registrar_pago_prefactura(renta_id):
    data = request.get_json()
    tipo = data.get('tipo', 'inicial')
    metodo = data.get('metodo_pago')
    monto = data.get('monto')
    monto_recibido = data.get('monto_recibido')
    cambio = data.get('cambio')
    facturable = data.get('facturable', False)
    numero_seguimiento = data.get('numero_seguimiento')

    # DEBUG: Verificar qué valor tiene facturable
    print(f"DEBUG: facturable recibido = {facturable}, tipo = {type(facturable)}")
    
    # Convertir explícitamente a entero para la BD
    facturable_int = 1 if facturable else 0
    print(f"DEBUG: facturable_int = {facturable_int}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertar prefactura con fecha_emision (NOW() toma la fecha/hora local del sistema)
        cursor.execute("""
            INSERT INTO prefacturas (
            renta_id, fecha_emision, tipo, pagada, metodo_pago, monto, 
            monto_recibido, cambio, numero_seguimiento, generada, facturable
        ) VALUES (%s, NOW() - INTERVAL 6 HOUR, %s, 1, %s, %s, %s, %s, %s, 1, %s)
""", (
    renta_id, tipo, metodo.upper(), monto, monto_recibido, cambio, 
    numero_seguimiento, facturable_int  
))
        prefactura_id = cursor.lastrowid

        # Actualizar renta
        cursor.execute("""
            UPDATE rentas SET estado_pago='Pago realizado', metodo_pago=%s WHERE id=%s
        """, (metodo.upper(), renta_id))
        
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'prefactura_id': prefactura_id})
    except Exception as e:
        print(f"Error al registrar prefactura: {e}")
        return jsonify({'success': False, 'error': str(e)})







@prefactura_bp.route('/pdf/<int:prefactura_id>')
def generar_pdf_prefactura(prefactura_id):
    # --- OBTENER DATOS COMPLETOS DEL CLIENTE ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, r.fecha_entrada, r.fecha_salida, r.direccion_obra, r.metodo_pago, r.iva,
               r.traslado, r.costo_traslado,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente,
               c.telefono,
               c.correo,
               c.calle,
               c.numero_exterior,
               c.numero_interior,
               c.entre_calles,
               c.colonia,
               c.codigo_postal,    
               c.municipio,
               c.estado,
               c.rfc
        FROM prefacturas p
        JOIN rentas r ON p.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE p.id = %s
    """, (prefactura_id,))
    prefactura = cursor.fetchone()

    cursor.execute("""
        SELECT prod.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
        FROM renta_detalle rd
        JOIN productos prod ON rd.id_producto = prod.id_producto
        WHERE rd.renta_id = %s
    """, (prefactura['renta_id'],))
    detalles = cursor.fetchall()
    cursor.close()
    conn.close()

    # --- GENERAR OVERLAY CON DATOS ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))

    # === INFORMACIÓN DEL CLIENTE ===
    can.setFont("Carlito", 12)
    
    # Código y nombre del cliente
    cliente_codigo_nombre = f"{prefactura['codigo_cliente']} - {prefactura['cliente_nombre']}"
    can.drawString(62, 695, f"{cliente_codigo_nombre}")
    
    # Teléfono
    can.drawString(69, 671, f"{prefactura['telefono'] or 'No registrado'}")
    
    # Correo
    can.drawString(61, 605, f"{prefactura['correo'] or 'No registrado'}")
    
    # Dirección (calle, número y entre calles)
    direccion_completa = prefactura['calle'] or ''
    if prefactura['numero_exterior']:
        direccion_completa += f" {prefactura['numero_exterior']}"
    if prefactura['numero_interior']:
        direccion_completa += f", Int. {prefactura['numero_interior']}"
    if prefactura['entre_calles']:
        direccion_completa += f" (entre {prefactura['entre_calles']})"
    if prefactura['colonia']:
        direccion_completa += f", COL. {prefactura['colonia']}"
    if prefactura['codigo_postal']:
        direccion_completa += f" - C.P. {prefactura['codigo_postal']}"

    
    can.drawString(73, 649, f"{direccion_completa}")
    
    # Estado y Municipio
    can.drawString(60, 626, f"{prefactura['estado'] or 'No registrado'}")
    can.drawString(280, 626, f"{prefactura['municipio'] or 'No registrado'}")
    
    # RFC
    can.drawString(254, 671, f"{prefactura['rfc'] or 'No registrado'}")
    
    # Facturable
    facturable_texto = "SÍ" if prefactura['facturable'] else "NO"
    can.drawString(443, 630, f"{facturable_texto}")
    
        # === FECHA Y HORA DE EMISIÓN (HORA DE CAMPECHE) ===
    can.setFont("Carlito", 9)
    # La fecha ya viene en hora de Campeche desde la BD
    fecha_emision = prefactura['fecha_emision']
    can.drawString(485, 710, f"{fecha_emision.strftime('%d/%m/%Y')}")
    can.drawString(529, 710, f" - {fecha_emision.strftime('%H:%M:%S')}")
    
    # Folio
    can.setFont("Carlito", 10)
    can.drawString(572, 725, f"#{prefactura_id}")

    # === TABLA DE PRODUCTOS ===
    can.setFont("Carlito", 10)
    
    # Datos de productos
    y = 550
    subtotal_general = 0
    
    for item in detalles:
        can.drawString(50, y, item['nombre'][:40])  # Limitar longitud del nombre
        can.drawRightString(347, y, str(item['cantidad']))
        can.drawRightString(405, y, str(item['dias_renta'] or 'N/A'))
        can.drawRightString(495, y, f"${item['costo_unitario']:.2f}")
        can.drawRightString(570, y, f"${item['subtotal']:.2f}")
        
        subtotal_general += float(item['subtotal'])
        y -= 18
        
        # Si hay muchos productos, crear nueva página o ajustar
        if y < 300:
            break

        # === LÍNEA DIVISORA Y TOTALES ===
    y -= 15
    can.line(28, y+10, 585, y+10)  # Línea separadora

    espacio_3mm = 13
    can.setFont("Carlito", 11)
    y_totales = y + 10 - espacio_3mm  # 3mm debajo de la línea

    # PERÍODO DE RENTA (AL LADO IZQUIERDO DEL SUBTOTAL)
    periodo_renta = f"{prefactura['fecha_salida'].strftime('%d/%m/%Y')}"
    if prefactura['fecha_entrada']:
        periodo_renta += f" - {prefactura['fecha_entrada'].strftime('%d/%m/%Y')}"
    else:
        periodo_renta += " - Indefinido"
    can.setFont("Carlito", 10)
    can.drawString(60, y_totales, f"PERIODO DE RENTA: {periodo_renta}")

    # Subtotal de productos (AL LADO DERECHO)
    can.setFont("Carlito", 11)
    can.drawString(400, y_totales, "SUBTOTAL:")
    can.drawRightString(570, y_totales, f"${subtotal_general:.2f}")
    y_totales -= 15

    # Traslado
    traslado_tipo = prefactura.get('traslado', 'ninguno')
    costo_traslado = prefactura.get('costo_traslado', 0)
    can.drawString(400, y_totales, f"TRASLADO ({traslado_tipo}):")
    can.drawRightString(570, y_totales, f"${costo_traslado:.2f}")
    y_totales -= 15

    # IVA
    can.drawString(400, y_totales, "IVA (16%):")
    can.drawRightString(570, y_totales, f"${prefactura['iva']:.2f}")
    y_totales -= 20

    # Total final
    can.setFont("Helvetica-Bold", 11)
    can.drawString(400, y_totales, "TOTAL:")
    can.drawRightString(570, y_totales, f"${prefactura['monto']:.2f}")

    # === MÉTODO DE PAGO (DEBAJO DEL TOTAL) ===
    y_totales -= 15
    can.setFont("Carlito", 11)
    can.drawString(400, y_totales, f"MÉTODO/PAGO: {prefactura['metodo_pago']}")

    # === TOTAL EN LETRAS (AL LADO IZQUIERDO) ===
    monto = prefactura['monto']
    monto_entero = int(monto)
    monto_centavos = int(round((monto - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"{monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"{monto_letras} PESOS 00/100 M.N."

    # Posicionar el total en letras al lado izquierdo del método de pago
    can.drawString(60, y_totales, f"SON: {monto_letras}")   
   

    # === AVISOS IMPORTANTES PARA EL CLIENTE ===
    y_avisos = y_totales - 25  # Más espacio entre totales y avisos

    # Línea separadora para los avisos
    can.line(28, y_avisos + 10, 585, y_avisos + 10)
    y_avisos -= 5

    # REQUISITOS DE CLIENTE
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DE CLIENTE:")
    y_avisos -= 15

    can.setFont("Helvetica", 8)
    can.drawString(60, y_avisos, "LOS SIGUIENTES DOCUMENTOS PUEDEN SER EN IMAGEN O EN COPIA IMPRESA:")
    y_avisos -= 12

    can.drawString(70, y_avisos, "• COPIA DE IDENTIFICACIÓN.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• COPIA LICENCIA DE CONDUCIR.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• COMPROBANTE DE DOMICILIO.")
    y_avisos -= 20

    # REQUISITOS DE RENTA
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DE RENTA:")
    y_avisos -= 15

    can.setFont("Helvetica", 8)
    can.drawString(70, y_avisos, "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO DE LA RENTA.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• UBICACIÓN EXACTA DE LA OBRA (POR GOOGLE MAPS)")
    y_avisos -= 20

    # ¡IMPORTANTE!
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "¡IMPORTANTE!")
    y_avisos -= 15

    can.setFont("Helvetica", 8)
    can.drawString(70, y_avisos, "• EL PERIODO DE RENTA INCLUYE DOMINGOS, DÍAS INHÁBILES Y FESTIVOS.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• NO SE ARMA, NI SE DESARMA EL EQUIPO.")








    # Guardar el canvas
    can.save()
    packet.seek(0)

    # --- COMBINAR CON LA PLANTILLA (SI TIENES) ---
    try:
        plantilla_path = os.path.join(current_app.root_path, 'static/notas/prefactura_plantilla.pdf')
        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()

            page = plantilla_pdf.pages[0]
            page.merge_page(overlay_pdf.pages[0])
            output.add_page(page)
        else:
            # Si no hay plantilla, usar solo el overlay
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            output.add_page(overlay_pdf.pages[0])
    except Exception as e:
        print(f"Error con plantilla, usando solo overlay: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        output.add_page(overlay_pdf.pages[0])

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    
    return send_file(
        output_stream, 
        download_name=f"prefactura_{prefactura_id}.pdf", 
        mimetype='application/pdf'
    )