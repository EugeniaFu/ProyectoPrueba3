# routes/notas_entrada.py
from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from utils.db import get_db_connection

notas_entrada_bp = Blueprint('notas_entrada', __name__, url_prefix='/notas_entrada')

@notas_entrada_bp.route('/registrar', methods=['POST'])
def registrar_nota_entrada():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        renta_id = request.form['renta_id']
        direccion_obra = request.form['direccion_obra']
        observaciones = request.form['observaciones']
        fecha_emision = datetime.now()

        cursor.execute("""
            INSERT INTO notas_entrada (renta_id, fecha_emision, direccion_obra, observaciones)
            VALUES (%s, %s, %s, %s)
        """, (renta_id, fecha_emision, direccion_obra, observaciones))

        nota_id = cursor.lastrowid

        piezas_ids = request.form.getlist('id_pieza[]')
        cantidades = request.form.getlist('cantidad[]')
        estados = request.form.getlist('estado[]')
        recargos = request.form.getlist('recargo[]')
        recibidos = request.form.getlist('recibido[]')

        for i in range(len(piezas_ids)):
            cursor.execute("""
                INSERT INTO entrada_detalle (nota_entrada_id, id_pieza, cantidad, estado, recargo, recibido)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                nota_id,
                piezas_ids[i],
                cantidades[i],
                estados[i],
                recargos[i],
                1 if recibidos[i] == '1' else 0
            ))

        conn.commit()
        flash("Nota de entrada registrada correctamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al registrar nota de entrada: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))
