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


# === Endpoint: Registrar pago y generar PDF (a implementar) ===
@prefactura_bp.route('/pago/<int:renta_id>', methods=['POST'])
def registrar_pago_prefactura(renta_id):
    from datetime import datetime

    data = request.get_json()
    tipo = data.get('tipo', 'inicial')
    metodo = data.get('metodo_pago')
    monto = data.get('monto')
    monto_recibido = data.get('monto_recibido')
    cambio = data.get('cambio')
    facturable = data.get('facturable', False)
    numero_seguimiento = data.get('numero_seguimiento')
    zona_horaria = str(datetime.now().astimezone().tzinfo)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertar prefactura
        cursor.execute("""
            INSERT INTO prefacturas (
                renta_id, tipo, pagada, metodo_pago, monto, monto_recibido, cambio, numero_seguimiento, zona_horaria, generada, facturable
            ) VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (
            renta_id, tipo, metodo, monto, monto_recibido, cambio, numero_seguimiento, zona_horaria, facturable
        ))
        prefactura_id = cursor.lastrowid  # Obtener el ID de la prefactura recién creada

        # Actualizar renta
        cursor.execute("""
            UPDATE rentas SET estado_pago='Pago realizado', metodo_pago=%s WHERE id=%s
        """, (metodo, renta_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'prefactura_id': prefactura_id})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'error': str(e)})















@prefactura_bp.route('/pdf/<int:prefactura_id>')
def generar_pdf_prefactura(prefactura_id):
    # --- OBTENER DATOS DE LA BD ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, r.fecha_entrada, r.fecha_salida, r.direccion_obra, r.metodo_pago, r.iva,
                   r.traslado, r.costo_traslado,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.telefono AS celular,
               c.codigo_cliente
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

    # Ajusta las posiciones X, Y según tu plantilla
    can.setFont("Carlito", 13)
    can.drawString(65, 701, prefactura['cliente_nombre'])  # NOMBRE
    can.drawString(65, 685, prefactura['celular'])         # CELULAR
    can.drawString(101, 669, prefactura['metodo_pago'])    # FORMA DE PAGO
    can.drawString(112, 651, f"{prefactura['fecha_salida'].strftime('%d/%m/%Y')} - {prefactura['fecha_entrada'].strftime('%d/%m/%Y') if prefactura['fecha_entrada'] else 'Indefinido'}")  # PERIODO DE RENTA
    can.drawString(417, 697, prefactura['fecha_emision'].strftime('%d/%m/%Y'))  # FECHA
    can.drawString(559, 732, f"# {prefactura['folio']}" if 'folio' in prefactura else f"# {prefactura_id}")  # FOLIO de nota)  # FOLIO de nota

    # --- TABLA DE PRODUCTOS ---
    y = 610
    can.setFont("Carlito", 13)
    subtotal_general = 0  # Suma de subtotales de productos
    for item in detalles:
        can.drawString(60, y, item['nombre'])  # DESCRIPCIÓN
        can.drawRightString(354, y, str(item['cantidad']))  # CANT.
        can.drawRightString(407, y, str(item['dias_renta']))  # DÍAS
        can.drawRightString(506, y, f"${item['costo_unitario']:.2f}")  # COSTO
        can.drawRightString(588, y, f"${item['subtotal']:.2f}")  # SUBTOTAL
        subtotal_general += float(item['subtotal'])
        y -= 18

    # --- TOTALES ---
    can.setFont("Carlito", 11)
    monto = prefactura['monto']
    monto_entero = int(monto)
    monto_centavos = int(round((monto - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"{monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"{monto_letras} PESOS 00/100 M.N."
    can.drawString(44, 487, monto_letras)
    
    can.setFont("Carlito", 13)
    can.drawRightString(592, 484, f"${subtotal_general:.2f}")  # SUBTOTAL (suma de productos)
    can.drawRightString(592, 453, f"${prefactura['iva']:.2f}")       # IVA
    
    can.setFont("Carlito", 13)
    can.drawRightString(592, 437, f"${prefactura['monto']:.2f}")     # TOTAL

        # --- TRASLADO ---
    traslado_tipo = prefactura.get('traslado', 'ninguno')
    costo_traslado = prefactura.get('costo_traslado', 0)

    # Texto a la izquierda
    can.setFont("Carlito", 11)
    can.drawString(462, 470, f"({traslado_tipo.capitalize()})")  # Ajusta X,Y según tu plantilla

    # Costo a la derecha
    can.setFont("Carlito", 13)
    can.drawRightString(592, 469, f"${costo_traslado:.2f}")  # Ajusta X,Y según tu plantilla

    # SOLO UNA VEZ, al final:
    can.save()
    packet.seek(0)

    # --- COMBINAR CON LA PLANTILLA ---
    plantilla_path = os.path.join(current_app.root_path, 'static/notas/plantilla_prefactura.pdf')
    plantilla_pdf = PdfReader(plantilla_path)
    overlay_pdf = PdfReader(packet)
    output = PdfWriter()

    page = plantilla_pdf.pages[0]
    page.merge_page(overlay_pdf.pages[0])
    output.add_page(page)

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    return send_file(output_stream, download_name=f"prefactura_{prefactura_id}.pdf", mimetype='application/pdf')

@prefactura_bp.route('/pdf_renta/<int:renta_id>')
def generar_pdf_prefactura_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Buscar prefactura por renta_id
    cursor.execute("SELECT id FROM prefacturas WHERE renta_id = %s ORDER BY id DESC LIMIT 1", (renta_id,))
    prefactura = cursor.fetchone()
    if not prefactura:
        return f"No hay prefactura para la renta {renta_id}", 404
    # Redirigir a la función original con el id de prefactura encontrado
    return redirect(url_for('prefactura.generar_pdf_prefactura', prefactura_id=prefactura['id']))
