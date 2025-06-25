from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from utils.db import get_db_connection
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from functools import wraps


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


SUCURSAL_PREFIJOS = {
    1: "01",  # Matriz
    2: "02",  # Los Reyes
    3: "03",  # Lerma
}

clientes_bp = Blueprint('clientes', __name__, url_prefix='/clientes')

@clientes_bp.route('/', methods=['GET'])
@requiere_permiso('ver_clientes')
def clientes():
    busqueda = request.args.get('busqueda', '').strip()
    filtro = request.args.get('filtro', '').strip()
    ver_bajas = request.args.get('ver_bajas', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Mostrar activos o inactivos según el filtro
    if ver_bajas == '1':
        query = "SELECT * FROM clientes WHERE activo = 0"
    else:
        query = "SELECT * FROM clientes WHERE activo = 1"
    params = []

    # Búsqueda por nombre, apellidos o teléfono
    if busqueda:
        query += " AND (nombre LIKE %s OR apellido1 LIKE %s OR apellido2 LIKE %s OR telefono LIKE %s)"
        like = f"%{busqueda}%"
        params.extend([like, like, like, like])

    # Filtro por tipo_cliente
    if filtro in ['betado', 'frecuente', 'ocasional']:
        query += " AND tipo_cliente = %s"
        params.append(filtro)

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'clientes/clientes.html',
        clientes=clientes,
        filtro=filtro,
        ver_bajas=ver_bajas
    )

@clientes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@requiere_permiso('editar_cliente')
def editar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        # Actualiza datos del cliente
        nombre = request.form['nombre']
        apellido1 = request.form['apellido1']
        apellido2 = request.form['apellido2']
        telefono = request.form['telefono']
        correo = request.form['correo']
        rfc = request.form['rfc']
        tipo_cliente = request.form['tipo_cliente']
        cursor.execute("""
            UPDATE clientes SET nombre=%s, apellido1=%s, apellido2=%s, telefono=%s, correo=%s, rfc=%s, tipo_cliente=%s
            WHERE id=%s
        """, (nombre, apellido1, apellido2, telefono, correo, rfc, tipo_cliente, id))

        # Eliminar documentos seleccionados
        ids_eliminar = request.form.getlist('eliminar_doc')
        if ids_eliminar:
            for doc_id in ids_eliminar:
                cursor.execute("DELETE FROM documentos_cliente WHERE id=%s AND cliente_id=%s", (doc_id, id))

        # Subir nuevos documentos
        archivos = request.files.getlist('documentos')
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clientes')
        os.makedirs(upload_folder, exist_ok=True)
        for idx, archivo in enumerate(archivos):
            if archivo and archivo.filename:
                filename = secure_filename(archivo.filename)
                ruta = os.path.join(upload_folder, filename)
                archivo.save(ruta)
                tipo_documento = request.form.get(f"tipo_documento_{idx}", "otro")
                cursor.execute("""
                    INSERT INTO documentos_cliente (cliente_id, tipo_documento, archivo)
                    VALUES (%s, %s, %s)
                """, (id, tipo_documento, filename))

        conn.commit()
        flash("Cliente actualizado correctamente.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for('clientes.clientes'))
    else:
        # Datos del cliente
        cursor.execute("SELECT * FROM clientes WHERE id=%s", (id,))
        cliente = cursor.fetchone()
        # Documentos actuales
        cursor.execute("SELECT * FROM documentos_cliente WHERE cliente_id=%s", (id,))
        documentos = cursor.fetchall()
        cursor.close()
        conn.close()
        if not cliente:
            flash("Cliente no encontrado.", "danger")
            return redirect(url_for('clientes.clientes'))
        return render_template('clientes/editar_cliente.html', cliente=cliente, documentos=documentos)



@clientes_bp.route('/baja/<int:id>')
@requiere_permiso('baja_cliente')
def baja_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clientes SET activo = 0 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Cliente dado de baja correctamente.", "info")
    return redirect(url_for('clientes.clientes'))



@clientes_bp.route('/reactivar/<int:id>')
@requiere_permiso('reactivar_cliente')
def reactivar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clientes SET activo = 1 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Cliente reactivado correctamente.", "success")
    return redirect(url_for('clientes.clientes', ver_bajas=1))



@clientes_bp.route('/eliminar/<int:id>')
@requiere_permiso('eliminar_cliente')
def eliminar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Cliente eliminado definitivamente.", "danger")
    return redirect(url_for('clientes.clientes', ver_bajas=1))

####################################
####################################
############################## visualizacion del cliente

@clientes_bp.route('/detalle/<int:id>')
@requiere_permiso('ver_detalle_cliente')
def detalle_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*, s.nombre AS sucursal_nombre
        FROM clientes c
        LEFT JOIN sucursales s ON c.sucursal_id = s.id
        WHERE c.id=%s
    """, (id,))
    cliente = cursor.fetchone()
    cursor.execute("SELECT * FROM documentos_cliente WHERE cliente_id=%s", (id,))
    documentos = cursor.fetchall()
    cursor.close()
    conn.close()
    if not cliente:
        flash("Cliente no encontrado.", "danger")
        return redirect(url_for('clientes.clientes'))
    return render_template('clientes/detalle_cliente.html', cliente=cliente, documentos=documentos)


####################################
####################################
############################## BUSCADOR

@clientes_bp.route('/buscar')
@requiere_permiso('buscar_clientes')
def buscar_clientes():
    term = request.args.get('q', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
    SELECT id, codigo_cliente, nombre, apellido1, apellido2, telefono, correo
    FROM clientes
    WHERE activo = 1 AND (
        codigo_cliente LIKE %s OR
        nombre LIKE %s OR
        apellido1 LIKE %s OR
        apellido2 LIKE %s OR
        CONCAT(nombre, ' ', apellido1, ' ', apellido2) LIKE %s OR
        telefono LIKE %s OR
        correo LIKE %s
    )
    LIMIT 10
    """
    like = f"%{term}%"
    cursor.execute(query, (like, like, like, like, like, like, like))
    try:
        id_int = int(term)
    except:
        id_int = 0
    cursor.execute(query, (like, like, like, like, id_int))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(results)

####################################
####################################
############################## NUEVO CLIENTE 

@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
@requiere_permiso('crear_cliente')
def nuevo_cliente():
    if request.method == 'POST':
        print("POST recibido")
        nombre = request.form['nombre']
        apellido1 = request.form['apellido1']
        apellido2 = request.form['apellido2']
        telefono = request.form['telefono']
        correo = request.form.get('correo')
        rfc = request.form.get('rfc')
        tipo_cliente = request.form['tipo_cliente']
        fecha_alta = datetime.now().strftime('%Y-%m-%d')
        archivos = request.files.getlist('documentos')

        sucursal_id = session.get('sucursal_id')

        print("Datos recibidos:", nombre, apellido1, apellido2, telefono, correo, rfc, tipo_cliente, "Sucursal:", sucursal_id)
        print("Archivos recibidos:", [a.filename for a in archivos])

        errores = []
        if not nombre or not apellido1 or not apellido2 or not telefono or not tipo_cliente:
            errores.append("Todos los campos obligatorios deben estar llenos.")
        if not any(archivo.filename for archivo in archivos):
            errores.append("Debes subir al menos un documento (INE, Licencia o Comprobante).")
        if not sucursal_id:
            errores.append("No se pudo identificar la sucursal del usuario. Vuelve a iniciar sesión.")

        # Validación de duplicados por teléfono
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes WHERE telefono = %s AND activo = 1", (telefono,))
        if cursor.fetchone():
            errores.append("Ya existe un cliente registrado con ese número de teléfono.")
        # Validación de duplicados por correo (si se proporciona)
        if correo:
            cursor.execute("SELECT * FROM clientes WHERE correo = %s AND activo = 1", (correo,))
            if cursor.fetchone():
                errores.append("Ya existe un cliente registrado con ese correo.")

        if errores:
            print("Errores de validación:", errores)
            for error in errores:
                flash(error, 'danger')
            cursor.close()
            conn.close()
            return render_template('clientes/nuevo_cliente.html')

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clientes (nombre, apellido1, apellido2, telefono, correo, rfc, tipo_cliente, sucursal_id, fecha_alta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, apellido1, apellido2, telefono, correo, rfc, tipo_cliente, sucursal_id, fecha_alta))
            cliente_id = cursor.lastrowid

            # === BLOQUE PARA GENERAR EL CODIGO_CLIENTE DINAMICO ===
            prefijo = SUCURSAL_PREFIJOS.get(int(sucursal_id), "00")
            # Busca el máximo consecutivo ya usado para esa sucursal
            cursor.execute("SELECT MAX(CAST(SUBSTRING(codigo_cliente, 3, 5) AS UNSIGNED)) FROM clientes WHERE sucursal_id = %s", (sucursal_id,))
            max_consecutivo = cursor.fetchone()[0] or 0
            consecutivo = max_consecutivo + 1
            consecutivo_str = str(consecutivo).zfill(5)
            codigo_cliente = f"{prefijo}{consecutivo_str}"
            cursor.execute("UPDATE clientes SET codigo_cliente = %s WHERE id = %s", (codigo_cliente, cliente_id))

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clientes')
            os.makedirs(upload_folder, exist_ok=True)
            for idx, archivo in enumerate(archivos):
                if archivo and archivo.filename:
                    filename = secure_filename(archivo.filename)
                    ruta = os.path.join(upload_folder, filename)
                    archivo.save(ruta)
                    tipo_documento = request.form.get(f"tipo_documento_{idx}", "otro")
                    cursor.execute("""
                        INSERT INTO documentos_cliente (cliente_id, tipo_documento, archivo)
                        VALUES (%s, %s, %s)
                    """, (cliente_id, tipo_documento, filename))
            conn.commit()
            cursor.close()
            conn.close()
            print("Cliente guardado correctamente.")
            flash("Cliente registrado exitosamente.", "success")
            return redirect(url_for('clientes.clientes'))
        except Exception as e:
            print("Error al guardar en la base de datos:", e)
            flash("Ocurrió un error al guardar el cliente.", "danger")
            return render_template('clientes/nuevo_cliente.html')

    return render_template('clientes/nuevo_cliente.html')