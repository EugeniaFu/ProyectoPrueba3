from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask import jsonify
from datetime import datetime
from utils.db import get_db_connection

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO



rentas_bp = Blueprint('rentas', __name__, url_prefix='/rentas')

@rentas_bp.route('/')
def modulo_rentas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consulta principal de rentas con cliente
    cursor.execute("""
        SELECT 
            r.id, r.fecha_registro, r.fecha_salida, r.fecha_entrada,
            r.estado_renta, r.estado_pago, r.metodo_pago,
            r.total_con_iva, r.total, r.iva, r.observaciones,
            r.direccion_obra,
            c.nombre, c.apellido1, c.apellido2
        FROM rentas r
        JOIN clientes c ON r.cliente_id = c.id
        ORDER BY r.fecha_registro DESC
    """)
    rentas = cursor.fetchall()

    # Detalles por renta
    cursor.execute("""
        SELECT d.renta_id, p.nombre, d.cantidad, d.id_producto, p.tipo
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
    """)
    detalles = cursor.fetchall()

    # Agrupar productos por renta
    productos_por_renta = {}
    for renta_id, nombre, cantidad, id_producto, tipo in detalles:
        productos_por_renta.setdefault(renta_id, []).append(f"{nombre} x{cantidad}")

    # Clientes activos
    cursor.execute("SELECT id, nombre, apellido1 FROM clientes WHERE activo = 1")
    clientes = cursor.fetchall()

    # Productos y precios (JOIN con producto_precios)
    cursor.execute("""
        SELECT p.id_producto, p.nombre, 
               pp.precio_dia, pp.precio_7dias, pp.precio_15dias, pp.precio_30dias, pp.precio_31mas, p.precio_unico
        FROM productos p
        JOIN producto_precios pp ON p.id_producto = pp.id_producto
        WHERE p.estatus = 'activo'
        ORDER BY p.nombre
    """)
    productos = cursor.fetchall()

    # Prepara los precios para JS
    precios_productos = {}
    for prod in productos:
        precios_productos[prod[0]] = {
            "precio_dia": float(prod[2]),
            "precio_7dias": float(prod[3]),
            "precio_15dias": float(prod[4]),
            "precio_30dias": float(prod[5]),
            "precio_31mas": float(prod[6]),
            "precio_unico": int(prod[7])
        }

    # Sucursal actual
    sucursal_id = session.get('sucursal_id')
    sucursal_nombre = None
    if sucursal_id:
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        row = cursor.fetchone()
        if row:
            sucursal_nombre = row[0]

    cursor.close()
    conn.close()

    return render_template(
        'rentas/index.html',
        rentas=rentas,
        clientes=clientes,
        productos=productos,
        productos_por_renta=productos_por_renta,
        sucursal_nombre=sucursal_nombre,
        precios_productos=precios_productos
    )

@rentas_bp.route('/crear', methods=['POST'])
def crear_renta():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.form.get('renta_programada'):
            estado_renta = 'programada'
        else:
            estado_renta = 'en curso'
        estado_pago = 'Pago pendiente'
        metodo_pago = 'Pendiente'
        cliente_id = request.form['cliente_id']
        direccion_obra = request.form['direccion_obra']
        fecha_salida = request.form['fecha_salida']
        fecha_entrada = request.form.get('fecha_entrada') or None
        observaciones = request.form.get('observaciones')
        fecha_registro = datetime.now()
        fecha_programada = request.form.get('fecha_programada') or None
        costo_traslado = float(request.form.get('costo_traslado') or 0)
        sucursal_id = session.get('sucursal_id')

        cursor.execute("""
            INSERT INTO rentas (
                cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                direccion_obra, estado_renta, estado_pago, metodo_pago,
                total, iva, total_con_iva, observaciones, fecha_programada, sucursal_id, costo_traslado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente_id, fecha_registro, fecha_salida, fecha_entrada,
            direccion_obra, estado_renta, estado_pago, metodo_pago,
            0, 0, 0, observaciones, fecha_programada, sucursal_id, costo_traslado
        ))

        renta_id = cursor.lastrowid

        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')

        total = 0

        for i in range(len(productos)):
            prod_id = int(productos[i])
            cant = int(cantidades[i])
            dias_renta_raw = dias[i]
            if dias_renta_raw in (None, '', 'null'):
                dias_renta = None  # o 0 si tu base no acepta NULL
                subtotal = 0
            else:
                dias_renta = int(dias_renta_raw)
                costo_unitario = float(costos[i])
                subtotal = cant * dias_renta * costo_unitario
                total += subtotal

            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                renta_id, prod_id, cant, dias_renta,
                float(costos[i]), subtotal
            ))

        # Calcular IVA y total con IVA
        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        cursor.execute("""
            UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
        """, (total, iva, total_con_iva, renta_id))

        conn.commit()
        flash("Renta registrada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al guardar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))

# Ejemplo de endpoint para cerrar renta y actualizar días/subtotales
@rentas_bp.route('/cerrar/<int:renta_id>', methods=['POST'])
def cerrar_renta(renta_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        fecha_entrada = request.form.get('fecha_entrada')
        if not fecha_entrada:
            flash("Debes ingresar la fecha de entrada para cerrar la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        # Obtener fecha_salida de la renta
        cursor.execute("SELECT fecha_salida FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        if not row:
            flash("Renta no encontrada.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))
        fecha_salida = row[0]

        # Calcular días de renta
        dias_renta = (datetime.strptime(fecha_entrada, "%Y-%m-%d") - datetime.strptime(str(fecha_salida), "%Y-%m-%d")).days + 1
        if dias_renta < 1:
            dias_renta = 1

        # Actualizar cada detalle de la renta
        cursor.execute("""
            SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        detalles = cursor.fetchall()
        for detalle in detalles:
            detalle_id, cantidad, costo_unitario = detalle
            subtotal = cantidad * dias_renta * costo_unitario
            cursor.execute("""
                UPDATE renta_detalle
                SET dias_renta = %s, subtotal = %s
                WHERE id = %s
            """, (dias_renta, subtotal, detalle_id))

        # Recalcular totales
        cursor.execute("""
            SELECT SUM(subtotal) FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        total = cursor.fetchone()[0] or 0

        # Obtener costo_traslado
        cursor.execute("SELECT costo_traslado FROM rentas WHERE id = %s", (renta_id,))
        costo_traslado = cursor.fetchone()[0] or 0

        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        cursor.execute("""
            UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s, estado_renta='cerrada'
            WHERE id=%s
        """, (fecha_entrada, total, iva, total_con_iva, renta_id))

        conn.commit()
        flash("Renta cerrada y actualizada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))





################################3
#################################
###################################




@rentas_bp.route('/prefactura/<int:renta_id>')
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
    # Totales
    cursor.execute("""
        SELECT total_con_iva FROM rentas WHERE id = %s
    """, (renta_id,))
    total = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "detalle": detalle,
        "total_con_iva": total['total_con_iva'] if total else 0
    })






@rentas_bp.route('/prefactura/pago/<int:renta_id>', methods=['POST'])
def registrar_pago_prefactura(renta_id):
    import pytz
    import json
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    import os

    data = request.get_json()
    tipo = data.get('tipo', 'inicial')
    metodo = data.get('metodo_pago')
    monto = data.get('monto')
    monto_recibido = data.get('monto_recibido')
    cambio = data.get('cambio')
    numero_seguimiento = data.get('numero_seguimiento')
    zona_horaria = str(datetime.now().astimezone().tzinfo)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertar prefactura
        cursor.execute("""
            INSERT INTO prefacturas (
                renta_id, tipo, pagada, metodo_pago, monto, monto_recibido, cambio, numero_seguimiento, zona_horaria, generada
            ) VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, 1)
        """, (
            renta_id, tipo, metodo, monto, monto_recibido, cambio, numero_seguimiento, zona_horaria
        ))

        # Actualizar renta
        cursor.execute("""
            UPDATE rentas SET estado_pago='Pago realizado', metodo_pago=%s WHERE id=%s
        """, (metodo, renta_id))
        conn.commit()

        # --- GENERAR PDF DE PREFACTURA ---
        # 1. Obtener datos de la renta y cliente
        cursor.execute("""
            SELECT r.fecha_registro, r.fecha_salida, r.fecha_entrada, r.direccion_obra, r.total_con_iva, r.total, r.iva, 
                   c.nombre, c.apellido1, c.apellido2, c.celular
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (renta_id,))
        renta = cursor.fetchone()

        cursor.execute("""
            SELECT p.nombre, d.cantidad, d.dias_renta, d.costo_unitario, d.subtotal
            FROM renta_detalle d
            JOIN productos p ON d.id_producto = p.id_producto
            WHERE d.renta_id = %s
        """, (renta_id,))
        detalle = cursor.fetchall()

        cursor.close()
        conn.close()

        # 2. Crear PDF de datos en memoria
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(396, 612))  # Media carta en puntos

        # Ejemplo de posiciones (ajusta según tu plantilla)
        can.setFont("Helvetica-Bold", 10)
        can.drawString(70, 540, f"{renta[7]} {renta[8]} {renta[9]}")  # Nombre
        can.setFont("Helvetica", 10)
        can.drawString(70, 525, f"{renta[10]}")  # Celular
        can.drawString(70, 510, f"{metodo}")    # Forma de pago
        can.drawString(70, 495, f"{renta[1]} a {renta[2]}")  # Periodo de renta
        can.drawString(300, 540, f"{renta[0]}")  # Fecha (ajusta según tu plantilla)
        can.drawString(300, 525, f"{renta_id}")  # Folio de salida
        can.drawString(300, 510, f"{renta[3]}")  # Obra

        # Tabla de productos (ajusta posiciones y formato)
        y = 470
        for item in detalle:
            can.drawString(55, y, str(item[0]))  # Descripción
            can.drawString(180, y, str(item[1])) # Cantidad
            can.drawString(210, y, str(item[2])) # Días
            can.drawString(250, y, f"${item[3]:.2f}") # Costo
            can.drawString(300, y, f"${item[4]:.2f}") # Subtotal
            y -= 15

        # Totales
        can.drawString(300, 120, f"${renta[5]:.2f}")  # Subtotal
        can.drawString(300, 105, f"${renta[6]:.2f}")  # IVA
        can.drawString(300, 90, f"${renta[4]:.2f}")   # Total

        can.save()
        packet.seek(0)

        # 3. Leer plantilla y superponer datos
        plantilla_path = os.path.join('static', 'notas', 'plantilla_prefactura.pdf')
        pdf_path = os.path.join('static', 'notas', f'prefactura_{renta_id}.pdf')
        plantilla = PdfReader(open(plantilla_path, "rb"))
        datos_pdf = PdfReader(packet)
        writer = PdfWriter()
        page = plantilla.pages[0]
        page.merge_page(datos_pdf.pages[0])
        writer.add_page(page)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        return jsonify({'success': True})
    except Exception as e:
        print(e)
        return jsonify({'success': False})