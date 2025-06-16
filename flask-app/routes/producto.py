from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db import get_db_connection

bp_producto = Blueprint('producto', __name__, url_prefix='/producto')

# Mostrar productos
@bp_producto.route('/productos')
def productos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Traer productos y precios
    cursor.execute("""
        SELECT p.*, pr.precio_7dias, pr.precio_15dias, pr.precio_30dias, pr.precio_31mas
        FROM productos p
        LEFT JOIN producto_precios pr ON p.id_producto = pr.id_producto
        ORDER BY p.estatus DESC, p.nombre
    """)
    productos = cursor.fetchall()
    # Traer piezas asociadas a cada producto
    for producto in productos:
        cursor.execute("""
            SELECT pp.cantidad, pi.nombre_pieza
            FROM producto_piezas pp
            JOIN piezas pi ON pp.id_pieza = pi.id_pieza
            WHERE pp.id_producto = %s
        """, (producto['id_producto'],))
        producto['piezas'] = cursor.fetchall()
    # Traer piezas para el modal de alta/edición
    cursor.execute("SELECT * FROM piezas")
    piezas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario/productos.html', productos=productos, piezas=piezas)

# Crear producto
@bp_producto.route('/crear', methods=['POST'])
def crear_producto():
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    tipo = request.form['tipo']
    precio_7dias = request.form['precio_7dias']
    precio_15dias = request.form['precio_15dias']
    precio_30dias = request.form['precio_30dias']
    precio_31mas = request.form['precio_31mas']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO productos (nombre, descripcion, tipo, estatus)
        VALUES (%s, %s, %s, 'activo')
    """, (nombre, descripcion, tipo))
    id_producto = cursor.lastrowid

    # Insertar precios
    cursor.execute("""
        INSERT INTO producto_precios (id_producto, precio_7dias, precio_15dias, precio_30dias, precio_31mas)
        VALUES (%s, %s, %s, %s, %s)
    """, (id_producto, precio_7dias, precio_15dias, precio_30dias, precio_31mas))

    # Insertar piezas asociadas
    if tipo == 'individual':
        id_pieza = request.form['pieza_individual']
        cursor.execute("""
            INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
            VALUES (%s, %s, 1)
        """, (id_producto, id_pieza))
    elif tipo == 'conjunto':
        piezas_kit = request.form.getlist('pieza_kit[]')
        cantidades_kit = request.form.getlist('cantidad_kit[]')
        for id_pieza, cantidad in zip(piezas_kit, cantidades_kit):
            cursor.execute("""
                INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
                VALUES (%s, %s, %s)
            """, (id_producto, id_pieza, cantidad))

    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto guardado correctamente.', 'success')
    return redirect(url_for('producto.productos'))

# Editar producto
@bp_producto.route('/editar/<int:id_producto>', methods=['POST'])
def editar_producto(id_producto):
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    precio_7dias = request.form['precio_7dias']
    precio_15dias = request.form['precio_15dias']
    precio_30dias = request.form['precio_30dias']
    precio_31mas = request.form['precio_31mas']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Actualiza datos generales
    cursor.execute("""
        UPDATE productos SET nombre=%s, descripcion=%s WHERE id_producto=%s
    """, (nombre, descripcion, id_producto))
    cursor.execute("""
        UPDATE producto_precios SET precio_7dias=%s, precio_15dias=%s, precio_30dias=%s, precio_31mas=%s
        WHERE id_producto=%s
    """, (precio_7dias, precio_15dias, precio_30dias, precio_31mas, id_producto))

    # Elimina piezas asociadas actuales
    cursor.execute("DELETE FROM producto_piezas WHERE id_producto=%s", (id_producto,))

    # Detecta tipo de producto (individual o conjunto)
    tipo = None
    cursor.execute("SELECT tipo FROM productos WHERE id_producto=%s", (id_producto,))
    tipo_row = cursor.fetchone()
    if tipo_row:
        tipo = tipo_row[0]

    # Inserta nuevas piezas asociadas
    if tipo == 'individual':
        id_pieza = request.form['pieza_individual']
        cursor.execute("""
            INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
            VALUES (%s, %s, 1)
        """, (id_producto, id_pieza))
    elif tipo == 'conjunto':
        piezas_kit = request.form.getlist('pieza_kit[]')
        cantidades_kit = request.form.getlist('cantidad_kit[]')
        for id_pieza, cantidad in zip(piezas_kit, cantidades_kit):
            cursor.execute("""
                INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
                VALUES (%s, %s, %s)
            """, (id_producto, id_pieza, cantidad))

    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto guardado correctamente.', 'success')
    return redirect(url_for('producto.productos'))




# Dar de baja producto (descontinuar)
@bp_producto.route('/baja/<int:id_producto>', methods=['POST'])
def dar_baja_producto(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE productos SET estatus='descontinuado' WHERE id_producto=%s
    """, (id_producto,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto descontinuado correctamente.', 'warning')
    return redirect(url_for('producto.productos'))

# Dar de alta producto (activar)
@bp_producto.route('/alta/<int:id_producto>', methods=['POST'])
def dar_alta_producto(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE productos SET estatus='activo' WHERE id_producto=%s
    """, (id_producto,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto activado correctamente.', 'success')
    return redirect(url_for('producto.productos'))