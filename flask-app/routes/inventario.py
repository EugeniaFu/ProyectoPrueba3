from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection
from functools import wraps
from flask import session

def requiere_permiso(nombre_permiso):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            permisos = session.get('permisos', [])
            if nombre_permiso not in permisos:
                flash('No tienes permiso para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator



bp_inventario = Blueprint('inventario', __name__, url_prefix='/inventario')

@bp_inventario.route('/general')
@requiere_permiso('ver_inventario_general')
def inventario_general():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM sucursales")
    sucursales = cursor.fetchall()
    cursor.execute("""
        SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
               SUM(i.total) AS total_empresa
        FROM piezas p
        LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
        GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
    """)
    piezas = cursor.fetchall()
    for pieza in piezas:
        pieza['sucursales'] = {}
        for suc in sucursales:
            cursor.execute("""
                SELECT total, disponibles, rentadas, daniadas, en_reparacion
                FROM inventario_sucursal
                WHERE id_pieza=%s AND id_sucursal=%s
            """, (pieza['id_pieza'], suc['id']))
            datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
            pieza['sucursales'][suc['id']] = datos
    cursor.close()
    conn.close()
    return render_template('inventario/inventario_general.html', piezas=piezas, sucursales=sucursales)



@bp_inventario.route('/agregar_pieza_general', methods=['POST'])
@requiere_permiso('agregar_pieza_inventario_general')
def agregar_pieza_general():
    nombre_pieza = request.form['nombre_pieza']
    codigo_pieza = request.form['codigo_pieza']
    categoria = request.form.get('categoria', '')
    descripcion = request.form.get('descripcion', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_pieza FROM piezas WHERE codigo_pieza=%s", (codigo_pieza,))
    existe = cursor.fetchone()
    if existe:
        # Trae los datos para la tabla
        cursor.execute("SELECT id, nombre FROM sucursales")
        sucursales = cursor.fetchall()
        cursor.execute("""
            SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
                   SUM(i.total) AS total_empresa
            FROM piezas p
            LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
            GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
        """)
        piezas = cursor.fetchall()
        for pieza in piezas:
            pieza['sucursales'] = {}
            for suc in sucursales:
                cursor.execute("""
                    SELECT total, disponibles, rentadas, daniadas, en_reparacion
                    FROM inventario_sucursal
                    WHERE id_pieza=%s AND id_sucursal=%s
                """, (pieza['id_pieza'], suc['id']))
                datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
                pieza['sucursales'][suc['id']] = datos
        cursor.close()
        conn.close()
        # Renderiza la vista con el modal abierto y los datos previos
        return render_template(
            'inventario/inventario_general.html',
            piezas=piezas,
            sucursales=sucursales,
            show_modal_nueva_pieza=True,
            error_codigo='El código ingresado ya existe. Por favor ingresa uno diferente.',
            form_data={
                'nombre_pieza': nombre_pieza,
                'codigo_pieza': codigo_pieza,
                'categoria': categoria,
                'descripcion': descripcion
            }
        )
    # Si no existe, inserta normalmente
    cursor.execute(
        "INSERT INTO piezas (codigo_pieza, nombre_pieza, categoria, descripcion) VALUES (%s, %s, %s, %s)",
        (codigo_pieza, nombre_pieza, categoria, descripcion)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))



@bp_inventario.route('/editar_pieza/<int:id_pieza>', methods=['POST'])
@requiere_permiso('modificar_existencias_inventario_general')
def editar_pieza(id_pieza):
    nombre_pieza = request.form['nombre_pieza']
    codigo_pieza = request.form['codigo_pieza']
    categoria = request.form.get('categoria', '')
    descripcion = request.form.get('descripcion', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Verifica si ya existe el código en otra pieza
    cursor.execute("SELECT id_pieza FROM piezas WHERE codigo_pieza=%s AND id_pieza!=%s", (codigo_pieza, id_pieza))
    existe = cursor.fetchone()
    if existe:
        # Trae los datos para la tabla
        cursor.execute("SELECT id, nombre FROM sucursales")
        sucursales = cursor.fetchall()
        cursor.execute("""
            SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
                   SUM(i.total) AS total_empresa
            FROM piezas p
            LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
            GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
        """)
        piezas = cursor.fetchall()
        for pieza in piezas:
            pieza['sucursales'] = {}
            for suc in sucursales:
                cursor.execute("""
                    SELECT total, disponibles, rentadas, daniadas, en_reparacion
                    FROM inventario_sucursal
                    WHERE id_pieza=%s AND id_sucursal=%s
                """, (pieza['id_pieza'], suc['id']))
                datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
                pieza['sucursales'][suc['id']] = datos
        cursor.close()
        conn.close()
        # Renderiza la vista con el modal de editar abierto y los datos previos
        return render_template(
            'inventario/inventario_general.html',
            piezas=piezas,
            sucursales=sucursales,
            show_modal_editar_pieza=id_pieza,
            error_codigo_editar='El código ingresado ya existe en otra pieza. Por favor ingresa uno diferente.',
            form_data_editar={
                'nombre_pieza': nombre_pieza,
                'codigo_pieza': codigo_pieza,
                'categoria': categoria,
                'descripcion': descripcion
            }
        )
    # Si no existe, actualiza normalmente
    cursor.execute(
        "UPDATE piezas SET codigo_pieza=%s, nombre_pieza=%s, categoria=%s, descripcion=%s WHERE id_pieza=%s",
        (codigo_pieza, nombre_pieza, categoria, descripcion, id_pieza)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))



from flask import session

# ...existing code...

@bp_inventario.route('/alta_baja_pieza', methods=['POST'])
@requiere_permiso('modificar_existencias_inventario_general')
def alta_baja_pieza():
    id_pieza = request.form['id_pieza']
    id_sucursal = request.form['id_sucursal']
    cantidad = int(request.form['cantidad'])
    tipo = request.form['tipo']
    descripcion = request.form.get('descripcion', '') if tipo == 'baja' else None
    usuario_id = session.get('user_id')  # <-- Obtén el usuario de la sesión

    conn = get_db_connection()
    cursor = conn.cursor()
    # Verifica si ya existe registro
    cursor.execute("SELECT total FROM inventario_sucursal WHERE id_pieza=%s AND id_sucursal=%s", (id_pieza, id_sucursal))
    row = cursor.fetchone()
    if row:
        if tipo == 'alta':
            cursor.execute("""
                UPDATE inventario_sucursal 
                SET total=total+%s, disponibles=disponibles+%s 
                WHERE id_pieza=%s AND id_sucursal=%s
            """, (cantidad, cantidad, id_pieza, id_sucursal))
        elif tipo == 'baja':
            cursor.execute("""
                UPDATE inventario_sucursal 
                SET total=GREATEST(total-%s,0), disponibles=GREATEST(disponibles-%s,0) 
                WHERE id_pieza=%s AND id_sucursal=%s
            """, (cantidad, cantidad, id_pieza, id_sucursal))
    else:
        if tipo == 'alta':
            cursor.execute("""
                INSERT INTO inventario_sucursal 
                (id_pieza, id_sucursal, total, disponibles, rentadas, daniadas, en_reparacion) 
                VALUES (%s, %s, %s, %s, 0, 0, 0)
            """, (id_pieza, id_sucursal, cantidad, cantidad))
    # Registrar movimiento para reporte (ahora incluye usuario)
    cursor.execute("""
        INSERT INTO movimientos_inventario (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (id_pieza, id_sucursal, tipo, cantidad, descripcion, usuario_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))


@bp_inventario.route('/transferir_pieza', methods=['POST'])
@requiere_permiso('transferir_piezas_inventario')
def transferir_pieza():
    id_pieza = request.form['id_pieza']
    id_sucursal_origen = request.form['id_sucursal_origen']
    id_sucursal_destino = request.form['id_sucursal_destino']
    cantidad = int(request.form['cantidad'])
    usuario_id = session.get('user_id')  # <-- Obtén el usuario de la sesión

    conn = get_db_connection()
    cursor = conn.cursor()
    # Resta en origen
    cursor.execute("""
        UPDATE inventario_sucursal 
        SET total=GREATEST(total-%s,0), disponibles=GREATEST(disponibles-%s,0) 
        WHERE id_pieza=%s AND id_sucursal=%s
    """, (cantidad, cantidad, id_pieza, id_sucursal_origen))
    # Suma en destino (o crea si no existe)
    cursor.execute("SELECT total FROM inventario_sucursal WHERE id_pieza=%s AND id_sucursal=%s", (id_pieza, id_sucursal_destino))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            UPDATE inventario_sucursal 
            SET total=total+%s, disponibles=disponibles+%s 
            WHERE id_pieza=%s AND id_sucursal=%s
        """, (cantidad, cantidad, id_pieza, id_sucursal_destino))
    else:
        cursor.execute("""
            INSERT INTO inventario_sucursal 
            (id_pieza, id_sucursal, total, disponibles, rentadas, daniadas, en_reparacion) 
            VALUES (%s, %s, %s, %s, 0, 0, 0)
        """, (id_pieza, id_sucursal_destino, cantidad, cantidad))
    # Registrar movimiento de transferencia (ahora incluye usuario)
    cursor.execute("""
        INSERT INTO movimientos_inventario (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (id_pieza, id_sucursal_origen, 'transferencia_salida', cantidad, f'Transferencia a sucursal {id_sucursal_destino}', usuario_id))
    cursor.execute("""
        INSERT INTO movimientos_inventario (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (id_pieza, id_sucursal_destino, 'transferencia_entrada', cantidad, f'Transferencia desde sucursal {id_sucursal_origen}', usuario_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))


##################################
############################# INVENTARIO MATRIZ
####################################

@bp_inventario.route('/matriz')
@requiere_permiso('ver_inventario_sucursal')
def inventario_matriz():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM sucursales WHERE id=1")
    sucursal = cursor.fetchone()
    cursor.execute("""
        SELECT p.nombre_pieza, p.categoria, 
               IFNULL(i.total, 0) AS total, 
               IFNULL(i.disponibles, 0) AS disponibles, 
               IFNULL(i.rentadas, 0) AS rentadas, 
               IFNULL(i.daniadas, 0) AS daniadas, 
               IFNULL(i.en_reparacion, 0) AS en_reparacion, 
               IFNULL(i.stock_minimo, 0) AS stock_minimo
        FROM piezas p
        LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza AND i.id_sucursal=1
    """)
    piezas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario/inventario_matriz.html', piezas=piezas, sucursal=sucursal)



@bp_inventario.route('/mandar_a_reparacion', methods=['POST'])
@requiere_permiso('mandar_pieza_reparacion')
def mandar_a_reparacion():
    id_pieza = request.form['id_pieza']
    id_sucursal = request.form['id_sucursal']
    cantidad = int(request.form['cantidad'])

    conn = get_db_connection()
    cursor = conn.cursor()
    # Restar de dañadas, sumar a en_reparacion
    cursor.execute("""
        UPDATE inventario_sucursal
        SET daniadas = GREATEST(daniadas - %s, 0),
            en_reparacion = en_reparacion + %s
        WHERE id_pieza = %s AND id_sucursal = %s
    """, (cantidad, cantidad, id_pieza, id_sucursal))
    # Registrar movimiento

    usuario_id = session.get('user_id')
    cursor.execute("""
    INSERT INTO movimientos_inventario (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
    VALUES (%s, %s, %s, %s, %s, %s)
                   """, (id_pieza, id_sucursal, 'a_reparacion', cantidad, 'Enviado a reparación', usuario_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_matriz'))



@bp_inventario.route('/regresar_a_disponible', methods=['POST'])
@requiere_permiso('regresar_pieza_disponible')
def regresar_a_disponible():
    id_pieza = request.form['id_pieza']
    id_sucursal = request.form['id_sucursal']
    cantidad = int(request.form['cantidad'])

    conn = get_db_connection()
    cursor = conn.cursor()
    # Restar de en_reparacion, sumar a disponibles
    cursor.execute("""
        UPDATE inventario_sucursal
        SET en_reparacion = GREATEST(en_reparacion - %s, 0),
            disponibles = disponibles + %s
        WHERE id_pieza = %s AND id_sucursal = %s
    """, (cantidad, cantidad, id_pieza, id_sucursal))
    # Registrar movimiento
    usuario_id = session.get('user_id')
    cursor.execute("""
    INSERT INTO movimientos_inventario (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
    VALUES (%s, %s, %s, %s, %s, %s)
                   """, (id_pieza, id_sucursal, 'a_disponible', cantidad, 'Regresado a disponibles', usuario_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_matriz'))