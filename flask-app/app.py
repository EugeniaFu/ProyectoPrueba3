from flask import Flask, render_template, redirect, url_for
from flask_mail import Mail


from routes.login import login_bp
from routes.dashboard import dashboard_bp
from routes.clientes import clientes_bp
from routes.inventario import bp_inventario
from routes.producto import bp_producto
from routes.empleados import empleados_bp
from routes.usuarios import usuarios_bp
from routes.cotizaciones import cotizaciones_bp

from routes.rentas import rentas_bp
from routes.notas_entrada import notas_entrada_bp
from routes.notas_salida import notas_salida_bp
from routes.prefactura import prefactura_bp


app = Flask(__name__)
app.secret_key = 'clave-secreta'


@app.template_filter('estado_color')
def estado_color(estado):
    colores = {
        'activa': 'success',
        'programada': 'primary',
        'finalizada': 'secondary',
        'cancelada': 'danger',
        'renovada': 'info',
        'parcialmente devuelta': 'warning'
    }
    return colores.get(estado, 'dark')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alejandralopeez2003@gmail.com'
app.config['MAIL_PASSWORD'] = 'tcbo ndan smyc bqml'
app.config['MAIL_DEFAULT_SENDER'] = 'alejandralopeez2003@gmail.com'

mail = Mail(app)


app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(bp_inventario)
app.register_blueprint(bp_producto)
app.register_blueprint(empleados_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(cotizaciones_bp)

app.register_blueprint(rentas_bp)
app.register_blueprint(notas_entrada_bp)
app.register_blueprint(notas_salida_bp)
app.register_blueprint(prefactura_bp)





@app.route('/')
def home():
    return redirect(url_for('login.login'))
    
if __name__ == '__main__':
    app.run(debug=True)