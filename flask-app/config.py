# filepath: flask-app/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta'
    SQLALCHEMY_DATABASE_URI = (
        'mysql+mysqlconnector://usuario:localhost/pruebaandamios'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False