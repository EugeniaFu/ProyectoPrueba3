from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from utils.db import get_db_connection

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

    # Detalles por renta: nombre producto, cantidad, tipo, id_producto
    cursor.execute("""
        SELECT d.renta_id, p.nombre, d.cantidad, d.tipo_producto, d.id_producto
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
    """)
    detalles = cursor.fetchall()

    # Traer piezas por producto (solo kits las usarán)
    cursor.execute("""
        SELECT pp.id_producto, pi.nombre_pieza, pp.cantidad
        FROM producto_piezas pp
        JOIN piezas pi ON pp.id_pieza = pi.id_pieza
    """)
    piezas_raw = cursor.fetchall()

    # Agrupar piezas por producto
    piezas_por_producto = {}
    for id_producto, nombre_pieza, cantidad in piezas_raw:
        piezas_por_producto.setdefault(id_producto, []).append(f"{nombre_pieza} x{cantidad}")

    # Agrupar datos por renta
    productos_por_renta = {}
    tipos_por_renta = {}
    piezas_detalle_por_renta = {}

    for renta_id, nombre, cantidad, tipo, id_producto in detalles:
        productos_por_renta.setdefault(renta_id, []).append(f"{nombre} x{cantidad}")
        tipos_por_renta.setdefault(renta_id, []).append(tipo)

        # Si es kit, agrega las piezas desglosadas
        if tipo == 'kit' and id_producto in piezas_por_producto:
            piezas_detalle_por_renta.setdefault(renta_id, []).extend(piezas_por_producto[id_producto])

    # Clientes activos
    cursor.execute("SELECT id, nombre, apellido1 FROM clientes WHERE activo = 1")
    clientes = cursor.fetchall()

    # Productos disponibles
    cursor.execute("SELECT id_producto, nombre FROM productos ORDER BY nombre")
    productos = cursor.fetchall()

    # Obtener piezas individuales
    cursor.execute("SELECT id_pieza, nombre_pieza FROM piezas ORDER BY nombre_pieza")
    piezas = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('rentas/index.html', 
                           rentas=rentas, 
                           clientes=clientes, 
                           productos_por_renta=productos_por_renta, 
                           piezas=piezas,
                           productos=productos,
                           tipos_por_renta=tipos_por_renta,
                           piezas_detalle_por_renta=piezas_detalle_por_renta)

@rentas_bp.route('/crear', methods=['POST'])
def crear_renta():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cliente_id = request.form['cliente_id']
        direccion_obra = request.form['direccion_obra']
        fecha_salida = request.form['fecha_salida']
        fecha_entrada = request.form.get('fecha_entrada') or None
        estado_renta = request.form['estado_renta']
        estado_pago = request.form['estado_pago']
        metodo_pago = request.form.get('metodo_pago')
        observaciones = request.form.get('observaciones')
        fecha_registro = datetime.now()

        # Insertar la renta (sin tipo_producto)
        cursor.execute("""
            INSERT INTO rentas (
                cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                direccion_obra, estado_renta, estado_pago, metodo_pago,
                total, iva, total_con_iva, observaciones
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente_id, fecha_registro, fecha_salida, fecha_entrada,
            direccion_obra, estado_renta, estado_pago, metodo_pago,
            0, 0, 0, observaciones
        ))

        renta_id = cursor.lastrowid

        # Obtener productos enviados desde el formulario
        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')
        tipos = request.form.getlist('tipo_producto[]')  # <-- aquí está el tipo

        total = 0

        for i in range(len(productos)):
            prod_id = int(productos[i])
            cant = int(cantidades[i])
            dias_renta = int(dias[i])
            costo_unitario = float(costos[i])
            tipo_producto = tipos[i]  # <-- 'pieza' o 'kit'
            subtotal = cant * dias_renta * costo_unitario
            total += subtotal

            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal, tipo_producto
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                renta_id, prod_id, cant, dias_renta,
                costo_unitario, subtotal, tipo_producto
            ))

        # Calcular IVA y total con IVA
        iva = total * 0.16
        total_con_iva = total + iva

        # Actualizar la renta con totales
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