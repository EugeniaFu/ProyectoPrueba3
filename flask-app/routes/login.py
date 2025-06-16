from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from argon2 import PasswordHasher
from utils.db import get_db_connection

conn = get_db_connection()


login_bp = Blueprint('login', __name__, url_prefix='/login')
ph = PasswordHasher()


@login_bp.route('/check_email')
def check_email():
    email = request.args.get('email')
    exists = False
    if email:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM usuarios WHERE usuario=%s', (email,))
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
        cursor.execute('SELECT * FROM usuarios WHERE usuario=%s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            try:
                if ph.verify(user['password_hash'], password):
                    session['user_id'] = user['id']
                    session['rol_id'] = user['rol_id']
                    session['sucursal_id'] = user['sucursal_id']
                    return redirect(url_for('dashboard.dashboard'))
            except Exception:
                pass
        flash('Usuario o contraseña incorrectos', 'danger')
        return render_template('login/login.html')
    # Este return es para el método GET
    return render_template('login/login.html')



@login_bp.route('/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form['email']
        # Aquí iría la lógica para recuperación de contraseña (enviar correo, etc.)
        flash('Si el correo existe, se enviarán instrucciones para recuperar la contraseña.', 'info')
    return render_template('login/recover.html')