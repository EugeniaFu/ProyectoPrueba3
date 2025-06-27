# routes/notas_salida.py
from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from utils.db import get_db_connection

notas_salida_bp = Blueprint('notas_salida', __name__, url_prefix='/notas_salida')

@notas_salida_bp.route('/registrar', methods=['POST'])
def registrar_nota_salida():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        renta_id = request.form['renta_id']
        direccion_obra = request.form['direccion_obra']
        observaciones = request.form['observaciones']
        fecha_emision = datetime.now()

        cursor.execute("""
            INSERT INTO notas_salida (renta_id, fecha_emision, direccion_obra, observaciones)
            VALUES (%s, %s, %s, %s)
        """, (renta_id, fecha_emision, direccion_obra, observaciones))

        nota_id = cursor.lastrowid
        piezas_ids = request.form.getlist('id_pieza[]')
        cantidades = request.form.getlist('cantidad[]')

        for i in range(len(piezas_ids)):
            cursor.execute("""
                INSERT INTO salida_detalle (nota_salida_id, id_pieza, cantidad)
                VALUES (%s, %s, %s)
            """, (
                nota_id,
                piezas_ids[i],
                cantidades[i]
            ))

        conn.commit()
        flash("Nota de salida registrada correctamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al registrar nota de salida: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))


# routes/generar_pdf.py
from flask import Blueprint, render_template, make_response
import pdfkit
from utils.db import get_db_connection

pdf_bp = Blueprint('pdf', __name__, url_prefix='/pdf')

@pdf_bp.route('/nota_salida/<int:renta_id>')
def generar_pdf_salida(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM notas_salida WHERE renta_id = %s ORDER BY fecha_emision DESC LIMIT 1", (renta_id,))
    nota = cursor.fetchone()

    cursor.execute("""
        SELECT s.*, p.nombre FROM salida_detalle s
        JOIN piezas p ON s.id_pieza = p.id
        WHERE s.nota_salida_id = %s
    """, (nota['id'],))
    detalle = cursor.fetchall()

    html = render_template('pdf/nota_salida.html', nota=nota, detalle=detalle)
    pdf = pdfkit.from_string(html, False)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=nota_salida.pdf'
    return response
