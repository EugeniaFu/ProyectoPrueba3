import os
from io import BytesIO
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from utils.db import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch


prefactura_bp = Blueprint('prefactura', __name__, url_prefix='/prefactura')

@prefactura_bp.route('/guardar/<int:renta_id>', methods=['POST'])
def guardar_prefactura(renta_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO prefacturas (
                renta_id, fecha_emision, generada, tipo, pagada,
                metodo_pago, monto, monto_recibido, cambio, numero_seguimiento,
                observaciones, zona_horaria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            renta_id,
            datetime.now(),
            1,
            data.get("tipo"),
            1,
            data.get("metodo_pago"),
            data.get("monto"),
            data.get("monto_recibido") or 0,
            data.get("cambio") or 0,
            data.get("numero_seguimiento") or '',
            '',
            ''
        ))

        prefactura_id = cursor.lastrowid  # ✅ Aquí está la diferencia
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "prefactura_id": prefactura_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    
@prefactura_bp.route('/pdf/<int:prefactura_id>')
def generar_pdf_prefactura(prefactura_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Consulta principal
    cursor.execute("""
        SELECT p.*, r.fecha_entrada, r.fecha_salida
        FROM prefacturas p
        JOIN rentas r ON p.renta_id = r.id
        WHERE p.id = %s
    """, (prefactura_id,))
    prefactura = cursor.fetchone()

    if not prefactura:
        cursor.close()
        conn.close()
        return "No se encontró la prefactura", 404

    # Detalle
    cursor.execute("""
        SELECT p.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
        FROM renta_detalle rd
        JOIN productos p ON rd.id_producto = p.id_producto
        WHERE rd.renta_id = %s
    """, (prefactura['renta_id'],))
    detalles = cursor.fetchall()

    cursor.close()
    conn.close()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # LOGO (superior izquierda)
    logo_path = os.path.join(current_app.root_path, 'static/img/logo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, inch * 0.5, height - inch * 1.1, width=100, height=100, preserveAspectRatio=True, mask='auto')

    # DATOS EMPRESA - CENTRO SUPERIOR
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 50, "PUNTALES Y ANDAMIOS COLOSIO")

    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 65, "Dirección: CALLE ECUADOR #140, ENTRE AV. COLOSIO Y CALLE AZTECA, SANTA ANA")
    c.drawCentredString(width / 2, height - 80, "Correo: puntalesyandamioscolosio@hotmail.com  |  WhatsApp: (981) 203 2257")
    c.drawCentredString(width / 2, height - 93, "Teléfono: (981) 123 4567")

    # PREFECTURA INFO
    y = height - inch * 1.8
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, y, f"Prefactura #{prefactura_id}")
    y -= 20

    c.setFont("Helvetica", 12)
    c.drawString(inch, y, f"Fecha emisión: {prefactura['fecha_emision'].strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 20
    c.drawString(inch, y, f"Renta desde: {prefactura['fecha_entrada']} hasta {prefactura['fecha_salida']}")
    y -= 30

    # ENCABEZADO TABLA
    c.setFont("Helvetica-Bold", 12)
    c.drawString(inch, y, "Producto")
    c.drawString(3*inch, y, "Cantidad")
    c.drawString(4*inch, y, "Días")
    c.drawString(5*inch, y, "Costo unitario")
    c.drawString(6.5*inch, y, "Subtotal")
    y -= 15
    c.line(inch, y, 7.5*inch, y)
    y -= 15

    # DETALLE
    c.setFont("Helvetica", 12)
    for item in detalles:
        if y < inch:
            c.showPage()
            y = height - inch
        c.drawString(inch, y, item['nombre'])
        c.drawRightString(3.5*inch, y, str(item['cantidad']))
        c.drawRightString(4.5*inch, y, str(item['dias_renta']))
        c.drawRightString(6*inch, y, f"${item['costo_unitario']:.2f}")
        c.drawRightString(7.5*inch, y, f"${item['subtotal']:.2f}")
        y -= 20

    y -= 10
    c.line(inch, y, 7.5*inch, y)
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(7.5*inch, y, f"Total: ${prefactura['monto']:.2f}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return send_file(buffer, download_name=f"prefactura_{prefactura_id}.pdf", mimetype='application/pdf')
