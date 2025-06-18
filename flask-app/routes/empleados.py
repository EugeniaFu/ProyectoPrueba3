from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection
import secrets
from argon2 import PasswordHasher
from flask_mail import Message
from flask import current_app
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

empleados_bp = Blueprint('empleados', __name__, url_prefix='/empleados')


@empleados_bp.route('/')
@requiere_permiso('ver_empleados')
def empleados():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Filtros
    busqueda = request.args.get('busqueda', '').strip()
    sucursal = request.args.get('sucursal', '')
    estado = request.args.get('estado', '')

    query = """
        SELECT u.id, u.nombre, u.apellido1, u.apellido2, u.correo, u.estado,
               s.nombre AS sucursal, r.nombre AS rol, u.sucursal_id, u.rol_id
        FROM usuarios u
        JOIN sucursales s ON u.sucursal_id = s.id
        JOIN roles r ON u.rol_id = r.id
        WHERE 1=1
    """
    params = []

    if busqueda:
        query += " AND (u.nombre LIKE %s OR u.apellido1 LIKE %s OR u.apellido2 LIKE %s OR u.correo LIKE %s) "
        like = f"%{busqueda}%"
        params += [like, like, like, like]
    if sucursal:
        query += " AND u.sucursal_id = %s "
        params.append(sucursal)
    if estado:
        query += " AND u.estado = %s "
        params.append(estado)

    query += " ORDER BY u.estado DESC, u.nombre"

    cursor.execute(query, params)
    empleados = cursor.fetchall()
    cursor.execute("SELECT id, nombre FROM sucursales")
    sucursales = cursor.fetchall()
    cursor.execute("SELECT id, nombre FROM roles")
    roles = cursor.fetchall()

    # ...permisos por empleado igual que antes...
    for empleado in empleados:
        cursor.execute("""
            SELECT p.id, p.nombre, p.descripcion
            FROM permisos p
            JOIN roles_permisos rp ON p.id = rp.permiso_id
            WHERE rp.rol_id = %s AND rp.permitido = 1
        """, (empleado['rol_id'],))
        permisos_rol = cursor.fetchall()
        empleado['permisos_rol'] = permisos_rol

        cursor.execute("""
            SELECT permiso_id
            FROM usuarios_permisos
            WHERE usuario_id = %s AND permitido = 0
        """, (empleado['id'],))
        permisos_desactivados = [row['permiso_id'] for row in cursor.fetchall()]
        empleado['permisos_desactivados'] = permisos_desactivados

    return render_template(
        'empleados/empleados.html',
        empleados=empleados,
        sucursales=sucursales,
        roles=roles
    )


@empleados_bp.route('/nuevo', methods=['POST'])
@requiere_permiso('crear_empleado')
def nuevo_empleado():
    nombre = request.form['nombre']
    apellido1 = request.form['apellido1']
    apellido2 = request.form['apellido2']
    correo = request.form['correo']
    sucursal_id = request.form['sucursal_id']
    rol_id = request.form['rol_id']

    temp_password = secrets.token_urlsafe(10)
    ph = PasswordHasher()
    password_hash = ph.hash(temp_password)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO usuarios (nombre, apellido1, apellido2, correo, password_hash, rol_id, sucursal_id, estado, requiere_cambio_password)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'activo', TRUE)
    """, (nombre, apellido1, apellido2, correo, password_hash, rol_id, sucursal_id))
    conn.commit()
    try:
        msg = Message(
            subject="Bienvenido a Andamios Colosio",
            recipients=[correo],
            html=render_template(
                'login/bienvenida.html',
                nombre=nombre,
                correo=correo,
                temp_password=temp_password,
                login_url=url_for('login.login', _external=True),
                logo_url=url_for('static', filename='img/logo.png', _external=True),
                year=2025
            )
        )
        mail = current_app.extensions['mail']
        mail.send(msg)
        flash('Empleado registrado y correo enviado correctamente.', 'success')
    except Exception as e:
        flash(f'Empleado registrado, pero no se pudo enviar el correo: {e}', 'warning')

    return redirect(url_for('empleados.empleados'))




@empleados_bp.route('/editar/<int:id>', methods=['POST'])
@requiere_permiso('editar_empleado')
def editar_empleado(id):
    nombre = request.form['nombre']
    apellido1 = request.form['apellido1']
    apellido2 = request.form['apellido2']
    correo = request.form['correo']
    sucursal_id = request.form['sucursal_id']
    rol_id = request.form['rol_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios
        SET nombre=%s, apellido1=%s, apellido2=%s, correo=%s, sucursal_id=%s, rol_id=%s
        WHERE id=%s
    """, (nombre, apellido1, apellido2, correo, sucursal_id, rol_id, id))
    conn.commit()
    flash('Empleado actualizado correctamente.', 'success')
    return redirect(url_for('empleados.empleados'))

@empleados_bp.route('/baja/<int:id>')
@requiere_permiso('baja_empleado')
def baja_empleado(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET estado='inactivo' WHERE id=%s", (id,))
    conn.commit()
    flash('Empleado dado de baja.', 'warning')
    return redirect(url_for('empleados.empleados'))

@empleados_bp.route('/alta/<int:id>')
@requiere_permiso('alta_empleado')
def alta_empleado(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET estado='activo' WHERE id=%s", (id,))
    conn.commit()
    flash('Empleado reactivado.', 'success')
    return redirect(url_for('empleados.empleados'))




@empleados_bp.route('/permisos/<int:id>', methods=['POST'])
@requiere_permiso('gestionar_permisos_empleado')
def gestionar_permisos(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener permisos del rol del empleado
    cursor.execute("SELECT rol_id FROM usuarios WHERE id = %s", (id,))
    empleado = cursor.fetchone()
    if not empleado:
        flash('Empleado no encontrado.', 'danger')
        return redirect(url_for('empleados.empleados'))

    cursor.execute("""
        SELECT p.id
        FROM permisos p
        JOIN roles_permisos rp ON p.id = rp.permiso_id
        WHERE rp.rol_id = %s AND rp.permitido = 1
    """, (empleado['rol_id'],))
    permisos_rol = [row['id'] for row in cursor.fetchall()]

    # Permisos seleccionados en el formulario (solo los del rol)
    permisos_seleccionados = [int(key.replace('permiso_', '')) for key in request.form if key.startswith('permiso_') and int(key.replace('permiso_', '')) in permisos_rol]

    # Eliminar permisos personalizados existentes SOLO de los permisos del rol
    if permisos_rol:
        formato_in = ','.join(['%s'] * len(permisos_rol))
        sql = f"DELETE FROM usuarios_permisos WHERE usuario_id = %s AND permiso_id IN ({formato_in})"
        params = [id] + permisos_rol
        cursor.execute(sql, params)

    # Insertar nuevos permisos personalizados (solo los del rol)
    for permiso_id in permisos_rol:
        permitido = permiso_id in permisos_seleccionados
        cursor.execute(
            "INSERT INTO usuarios_permisos (usuario_id, permiso_id, permitido) VALUES (%s, %s, %s)",
            (id, permiso_id, permitido)
        )
    conn.commit()
    flash('Permisos actualizados correctamente.', 'success')
    return redirect(url_for('empleados.empleados'))