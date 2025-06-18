from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from argon2 import PasswordHasher
from utils.db import get_db_connection
import os
import re
from werkzeug.utils import secure_filename

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_bp.route('/perfil', methods=['GET', 'POST'])
def perfil():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.nombre, u.apellido1, u.apellido2, u.correo, u.sucursal_id, u.rol_id,
               u.foto_url, s.nombre AS sucursal_nombre, r.nombre AS rol_nombre
        FROM usuarios u
        JOIN sucursales s ON u.sucursal_id = s.id
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id=%s
    """, (user_id,))
    usuario = cursor.fetchone()

    if request.method == 'POST':
        nueva = request.form['nueva_contraseña']
        confirmar = request.form['confirmar_contraseña']
        if nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'danger')
        elif len(nueva) < 8 or not re.search(r'[A-Z]', nueva) or not re.search(r'[!@#$%^&*()_+\-=\[\]{};\'\\|,.<>\/?]', nueva):
            flash('La contraseña debe tener al menos 8 caracteres, una mayúscula y un carácter especial.', 'danger')
        else:
            ph = PasswordHasher()
            password_hash = ph.hash(nueva)
            cursor.execute("UPDATE usuarios SET password_hash=%s, requiere_cambio_password=FALSE WHERE id=%s", (password_hash, user_id))
            conn.commit()
            flash('Contraseña actualizada correctamente.', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard.dashboard'))
    cursor.close()
    conn.close()
    return render_template('usuarios/perfil.html', usuario=usuario)

@usuarios_bp.route('/cambiar_foto', methods=['POST'])
def cambiar_foto():
    user_id = session.get('user_id')
    if not user_id or 'foto_perfil' not in request.files:
        return redirect(url_for('usuarios.perfil'))
    foto = request.files['foto_perfil']
    if foto and foto.filename != '':
        filename = secure_filename(f"{user_id}_{foto.filename}")
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        ruta = os.path.join(upload_folder, filename)
        foto.save(ruta)
        foto_url = url_for('static', filename=f'uploads/{filename}')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET foto_url=%s WHERE id=%s", (foto_url, user_id))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('usuarios.perfil'))