import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='db-instance1.cpggcscass83.us-east-2.rds.amazonaws.com',
        user='admin',
        password='12345678',
        database='pruebacolosio'
    )
    return connection