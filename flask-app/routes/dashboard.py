from flask import Blueprint, render_template, session, redirect, url_for

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login.login'))
    return render_template('dashboard/dashboard.html')

@dashboard_bp.route('/cambiar_sucursal/<int:sucursal_id>')
def cambiar_sucursal(sucursal_id):
    session['sucursal_id'] = sucursal_id
    return redirect(url_for('dashboard.dashboard'))