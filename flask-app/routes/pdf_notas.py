from flask import Blueprint, make_response, render_template
from utils.db import get_db_connection
import pdfkit

pdf_bp = Blueprint('pdf', __name__, url_prefix='/pdf')

@pdf_bp.route('/nota_salida/<int:renta_id>')
def generar_pdf_salida(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ns.*, r.direccion_obra
        FROM notas_salida ns
        JOIN rentas r ON ns.renta_id = r.id
        WHERE ns.renta_id = %s
    """, (renta_id,))
    nota = cursor.fetchone()

    cursor.execute("""
        SELECT s.cantidad, p.nombre
        FROM salida_detalle s
        JOIN piezas p ON s.id_pieza = p.id
        WHERE s.nota_salida_id = %s
    """, (nota['id'],))
    detalle = cursor.fetchall()

    html = render_template('pdf/nota_salida.html', nota=nota, detalle=detalle)
    pdf = pdfkit.from_string(html, False)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=nota_salida_{renta_id}.pdf'
    return response

@pdf_bp.route('/nota_entrada/<int:renta_id>')
def generar_pdf_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ne.*, r.direccion_obra
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        WHERE ne.renta_id = %s
    """, (renta_id,))
    nota = cursor.fetchone()

    cursor.execute("""
        SELECT e.cantidad, e.estado, e.recargo, p.nombre
        FROM entrada_detalle e
        JOIN piezas p ON e.id_pieza = p.id
        WHERE e.nota_entrada_id = %s
    """, (nota['id'],))
    detalle = cursor.fetchall()

    html = render_template('pdf/nota_entrada.html', nota=nota, detalle=detalle)
    pdf = pdfkit.from_string(html, False)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=nota_entrada_{renta_id}.pdf'
    return response

@pdf_bp.route('/prefactura/<int:renta_id>')
def generar_pdf_prefactura(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.*, c.nombre, c.apellido1, c.apellido2
        FROM rentas r
        JOIN clientes c ON r.cliente_id = c.id
        WHERE r.id = %s
    """, (renta_id,))
    renta = cursor.fetchone()

    cursor.execute("""
        SELECT d.cantidad, d.dias_renta, d.costo_unitario, d.subtotal, p.nombre
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
        WHERE d.renta_id = %s
    """, (renta_id,))
    detalle = cursor.fetchall()

    html = render_template('pdf/prefactura.html', renta=renta, detalle=detalle)
    pdf = pdfkit.from_string(html, False)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=prefactura_{renta_id}.pdf'
    return response
