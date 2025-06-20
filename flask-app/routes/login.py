from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from argon2 import PasswordHasher
from utils.db import get_db_connection
import secrets
from datetime import datetime, timedelta
from flask_mail import Message

login_bp = Blueprint('login', __name__, url_prefix='/login')
ph = PasswordHasher()

@login_bp.route('/check_email')
def check_email():
    email = request.args.get('email')
    exists = False
    if email:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM usuarios WHERE correo=%s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            exists = True
    return jsonify({'exists': exists})

@login_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE correo=%s', (username,))
        user = cursor.fetchone()
        if user:
            try:
                    # ...existing code...
                if ph.verify(user['password_hash'], password):
                    session['user_id'] = user['id']
                    session['rol_id'] = user['rol_id']
                    session['sucursal_id'] = user['sucursal_id']

                    # Permisos por rol
                    cursor.execute("""
                        SELECT p.nombre
                        FROM permisos p
                        JOIN roles_permisos rp ON p.id = rp.permiso_id
                        WHERE rp.rol_id = %s AND rp.permitido = 1
                    """, (user['rol_id'],))
                    permisos_rol = {row['nombre'] for row in cursor.fetchall()}

                    # Permisos desactivados individualmente
                    cursor.execute("""
                        SELECT p.nombre
                        FROM permisos p
                        JOIN usuarios_permisos up ON p.id = up.permiso_id
                        WHERE up.usuario_id = %s AND up.permitido = 0
                    """, (user['id'],))
                    permisos_desactivados = {row['nombre'] for row in cursor.fetchall()}

                    # Permisos activados individualmente (opcional, si manejas excepciones positivas)
                    cursor.execute("""
                        SELECT p.nombre
                        FROM permisos p
                        JOIN usuarios_permisos up ON p.id = up.permiso_id
                        WHERE up.usuario_id = %s AND up.permitido = 1
                    """, (user['id'],))
                    permisos_activados = {row['nombre'] for row in cursor.fetchall()}

                    # Permisos finales: (rol + activados) - desactivados
                    permisos = list((permisos_rol | permisos_activados) - permisos_desactivados)
                    session['permisos'] = permisos

                    cursor.close()
                    conn.close()
                    # Redirección según si requiere cambio de contraseña
                    if user.get('requiere_cambio_password', False):
                        return redirect(url_for('usuarios.perfil'))
                    else:
                        return redirect(url_for('dashboard.dashboard'))
            except Exception:
                pass
        flash('Usuario o contraseña incorrectos', 'danger')
        return render_template('login/login.html')
    return render_template('login/login.html')


@login_bp.route('/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre FROM usuarios WHERE correo=%s", (email,))
        user = cursor.fetchone()
        if user:
            # Generar token seguro y fecha de expiración
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)
            cursor2 = conn.cursor()
            cursor2.execute(
                "INSERT INTO password_reset_tokens (usuario_id, token, expires_at) VALUES (%s, %s, %s)",
                (user['id'], token, expires_at)
            )
            conn.commit()
            # Enviar correo con el enlace
            reset_url = url_for('login.reset_password', token=token, _external=True)
            logo_url = url_for('static', filename='img/logo.png', _external=True)
            html_body = render_template(
                'login/email.html',
                nombre=user['nombre'],
                reset_url=reset_url,
                year=datetime.now().year,
                logo_url=logo_url
            )
            msg = Message(
                subject="Recupera tu contraseña - Andamios Colosio",
                recipients=[email],
                html=html_body
            )
            mail = current_app.extensions['mail']
            mail.send(msg)
        flash('Si el correo está registrado, recibirás un mensaje con instrucciones para restablecer tu contraseña.', 'info')
        return redirect(url_for('login.login'))
    return render_template('login/recover.html')

@login_bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.id, t.usuario_id, t.expires_at, t.usado, u.correo
        FROM password_reset_tokens t
        JOIN usuarios u ON t.usuario_id = u.id
        WHERE t.token=%s
    """, (token,))
    token_data = cursor.fetchone()
    if not token_data or token_data['usado'] or datetime.now() > token_data['expires_at']:
        flash('El enlace de recuperación es inválido o ha expirado.', 'danger')
        return redirect(url_for('login.recover'))

    if request.method == 'POST':
        nueva = request.form['nueva_contraseña']
        confirmar = request.form['confirmar_contraseña']
        import re
        if nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'danger')
        elif len(nueva) < 8 or not re.search(r'[A-Z]', nueva) or not re.search(r'\d', nueva) or not re.search(r'[!@#$%^&*()_+\-=\[\]{};\'\\|,.<>\/?]', nueva):
            flash('La contraseña debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial.', 'danger')
        else:
            ph = PasswordHasher()
            password_hash = ph.hash(nueva)
            cursor2 = conn.cursor()
            cursor2.execute("UPDATE usuarios SET password_hash=%s, requiere_cambio_password=FALSE WHERE id=%s", (password_hash, token_data['usuario_id']))
            cursor2.execute("UPDATE password_reset_tokens SET usado=TRUE WHERE id=%s", (token_data['id'],))
            conn.commit()
            flash('Contraseña restablecida correctamente. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login.login'))
    return render_template('login/reset_password.html')