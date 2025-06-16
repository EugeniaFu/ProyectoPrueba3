# filepath: flask-app/app.py
from flask import Flask, render_template, redirect, url_for
import mysql.connector


from routes.login import login_bp
from routes.dashboard import dashboard_bp
from routes.clientes import clientes_bp
from routes.inventario import bp_inventario
from routes.producto import bp_producto



app = Flask(__name__)
app.secret_key = 'clave-secreta'

app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(bp_inventario)
app.register_blueprint(bp_producto)


def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='123456',
        database='pruebaandamios'
    )
    return connection

@app.route('/')
def home():
    return redirect(url_for('login.login'))
    
if __name__ == '__main__':
    app.run(debug=True)