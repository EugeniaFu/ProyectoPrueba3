from flask import Blueprint, jsonify, request
from datetime import datetime
from utils.db import get_db_connection

notas_salida_bp = Blueprint('notas_salida', __name__, url_prefix='/notas_salida')

@notas_salida_bp.route('/preview/<int:renta_id>')
def preview_nota_salida(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Siguiente folio
    cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_salida")
    folio = str(cursor.fetchone()['siguiente_folio']).zfill(5)

    # 2. Datos de la renta y cliente
    cursor.execute("""
        SELECT r.fecha_salida, r.fecha_entrada, r.direccion_obra,
               c.nombre, c.apellido1, c.apellido2, c.telefono
        FROM rentas r
        JOIN clientes c ON r.cliente_id = c.id
        WHERE r.id = %s
    """, (renta_id,))
    renta = cursor.fetchone()
    if not renta:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Renta no encontrada'}), 404

    # 3. Periodo
    fecha_salida = renta['fecha_salida'].strftime('%d/%m/%Y') if renta['fecha_salida'] else '--/--/----'
    if renta['fecha_entrada']:
        fecha_entrada = renta['fecha_entrada'].strftime('%d/%m/%Y')
        periodo = f"{fecha_salida} a {fecha_entrada}"
    else:
        periodo = f"{fecha_salida} a indefinido"

    # 4. Desglose de piezas a entregar
    cursor.execute("""
        SELECT rd.id_producto, rd.cantidad
        FROM renta_detalle rd
        WHERE rd.renta_id = %s
    """, (renta_id,))
    productos = cursor.fetchall()

    piezas_dict = {}
    for prod in productos:
        id_producto = prod['id_producto']
        cantidad_producto = prod['cantidad']
        # Busca las piezas asociadas a este producto
        cursor.execute("""
            SELECT pp.id_pieza, pz.nombre_pieza, pp.cantidad
            FROM producto_piezas pp
            JOIN piezas pz ON pp.id_pieza = pz.id_pieza
            WHERE pp.id_producto = %s
        """, (id_producto,))
        piezas = cursor.fetchall()
        for pieza in piezas:
            id_pieza = pieza['id_pieza']
            nombre_pieza = pieza['nombre_pieza']
            cantidad_pieza = pieza['cantidad'] * cantidad_producto
            if id_pieza in piezas_dict:
                piezas_dict[id_pieza]['cantidad'] += cantidad_pieza
            else:
                piezas_dict[id_pieza] = {
                    'id_pieza': id_pieza,
                    'nombre_pieza': nombre_pieza,
                    'cantidad': cantidad_pieza
                }

    piezas_list = list(piezas_dict.values())

    cursor.close()
    conn.close()

    return jsonify({
        'folio': folio,
        'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'cliente': f"{renta['nombre']} {renta['apellido1']} {renta['apellido2']}",
        'celular': renta['telefono'],
        'direccion_obra': renta['direccion_obra'],
        'periodo': periodo,
        'piezas': piezas_list
    })


@notas_salida_bp.route('/crear/<int:renta_id>', methods=['POST'])
def crear_nota_salida(renta_id):
    data = request.get_json()
    numero_referencia = data.get('numero_referencia')
    observaciones = data.get('observaciones')
    piezas = data.get('piezas', [])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener siguiente folio
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_salida")
        folio = cursor.fetchone()['siguiente_folio']

        # Insertar nota de salida
        cursor.execute("""
            INSERT INTO notas_salida (folio, renta_id, fecha, numero_referencia, observaciones)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (folio, renta_id, numero_referencia, observaciones))
        nota_salida_id = cursor.lastrowid

        # Obtener la sucursal de la renta SOLO UNA VEZ
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        id_sucursal = row['id_sucursal'] if row else None

        # Insertar detalle de piezas y descontar inventario de la sucursal SOLO UNA VEZ POR PIEZA
        for pieza in piezas:
            id_pieza = pieza.get('id_pieza')
            cantidad = pieza.get('cantidad')
            if id_pieza and cantidad:
                print(f"UPDATE inventario_sucursal SET disponibles = disponibles - {cantidad}, rentadas = rentadas + {cantidad} WHERE id_sucursal = {id_sucursal} AND id_pieza = {id_pieza}")
                cursor.execute("""
                    INSERT INTO notas_salida_detalle (nota_salida_id, id_pieza, cantidad)
                    VALUES (%s, %s, %s)
                """, (nota_salida_id, id_pieza, cantidad))
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET disponibles = disponibles - %s,
                        rentadas = rentadas + %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad, cantidad, id_sucursal, id_pieza))
                print("Filas afectadas:", cursor.rowcount)

        # Cambiar estado de la renta a "Activo"
        cursor.execute("""
                       
            UPDATE rentas SET estado_renta = 'Activo' WHERE id = %s
        """, (renta_id,))

        conn.commit()
        return jsonify({'success': True, 'folio': folio})
    except Exception as e:
        conn.rollback()
        print(e)
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()