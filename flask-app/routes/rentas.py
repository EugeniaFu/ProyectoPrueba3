from flask import Blueprint, render_template

rentas_bp = Blueprint('rentas', __name__, url_prefix='/rentas')

@rentas_bp.route('/')
def modulo_rentas():
    return render_template('rentas/index.html')
