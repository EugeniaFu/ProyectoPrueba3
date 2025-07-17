from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask import jsonify
from datetime import datetime, timedelta  # <- AGREGAR timedelta aquí
from utils.db import get_db_connection

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO



rentas_bp = Blueprint('rentas', __name__, url_prefix='/rentas')



@rentas_bp.route('/')
def modulo_rentas():

    print(f"🕐 HORA ACTUAL DEL SERVIDOR: {datetime.now()}")
    print(f"📅 FECHA ACTUAL: {datetime.now().date()}")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consulta principal de rentas con cliente
    cursor.execute("""
        SELECT 
        r.id, r.fecha_registro, r.fecha_salida, r.fecha_entrada,
        r.estado_renta, r.estado_pago, r.metodo_pago,
        r.total_con_iva, r.total, r.iva, r.observaciones,
        r.direccion_obra,
        c.nombre, c.apellido1, c.apellido2,
        -- Verificar si ya tiene nota de entrada
        (SELECT COUNT(*) FROM notas_entrada ne WHERE ne.renta_id = r.id) as tiene_nota_entrada,
        -- Calcular fecha límite de entrega (un día después + 10:00 AM)
        CASE 
            WHEN r.fecha_entrada IS NOT NULL THEN 
                DATE_ADD(r.fecha_entrada, INTERVAL 1 DAY)
            ELSE NULL 
        END as fecha_limite_entrega
    FROM rentas r
    JOIN clientes c ON r.cliente_id = c.id
    ORDER BY r.fecha_registro DESC
""")           
    
    rentas = cursor.fetchall()

    if rentas:
        print("=== DATOS DE LA PRIMERA RENTA ===")
        for i, campo in enumerate(rentas[0]):
            print(f"Índice {i}: {campo}")


    # Detalles por renta
    cursor.execute("""
        SELECT d.renta_id, p.nombre, d.cantidad, d.id_producto, p.tipo
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
    """)
    detalles = cursor.fetchall()

    # Agrupar productos por renta
    productos_por_renta = {}
    for renta_id, nombre, cantidad, id_producto, tipo in detalles:
        productos_por_renta.setdefault(renta_id, []).append(f"{nombre} x{cantidad}")

    # Clientes activos
    cursor.execute("SELECT id, nombre, apellido1 FROM clientes WHERE activo = 1")
    clientes = cursor.fetchall()

    # Productos y precios (JOIN con producto_precios)
    cursor.execute("""
        SELECT p.id_producto, p.nombre, 
               pp.precio_dia, pp.precio_7dias, pp.precio_15dias, pp.precio_30dias, pp.precio_31mas, p.precio_unico
        FROM productos p
        JOIN producto_precios pp ON p.id_producto = pp.id_producto
        WHERE p.estatus = 'activo'
        ORDER BY p.nombre
    """)
    productos = cursor.fetchall()

    # Prepara los precios para JS
    precios_productos = {}
    for prod in productos:
        precios_productos[prod[0]] = {
            "precio_dia": float(prod[2]),
            "precio_7dias": float(prod[3]),
            "precio_15dias": float(prod[4]),
            "precio_30dias": float(prod[5]),
            "precio_31mas": float(prod[6]),
            "precio_unico": int(prod[7])
        }

            # Sucursal actual
    sucursal_id = session.get('sucursal_id')
    sucursal_nombre = None
    if sucursal_id:
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        row = cursor.fetchone()
        if row:
            sucursal_nombre = row[0]

    def calcular_estado_entrega(renta):
        """Calcula el estado de entrega de una renta (solo indicadores adicionales)"""

        print(f"=== DEBUG RENTA {renta[0]} ===")
        print(f"fecha_entrada: {renta[3]} (tipo: {type(renta[3])})")
        print(f"tiene_nota_entrada: {renta[15]} (tipo: {type(renta[15])})")
        print(f"estado_renta: {renta[4]}")

        # Si no tiene fecha de entrada definida, no mostrar indicador
        if not renta[3]:  # fecha_entrada
            print("❌ No tiene fecha de entrada")
            return None
        
        # Si ya tiene nota de entrada, no mostrar indicador (ya está finalizada)
        if renta[15]:  # ← CAMBIO: índice 15 (tiene_nota_entrada)
            print(f"❌Ya tiene nota de entrada: {renta[15]}")
            return None
        
        # Si el estado de la renta no es 'Activo', no mostrar indicador
        if renta[4] != 'Activo':  # estado_renta
            print(f"❌ Estado no es Activo: {renta[4]}")
            return None

        print("✅ Pasó todas las validaciones!")
        
        fecha_entrada = renta[3]  # fecha_entrada
        fecha_limite = renta[16]  # ← CAMBIO: índice 16 (fecha_limite_entrega)
        ahora = datetime.now()

        print(f"fecha_entrada: {fecha_entrada}")
        print(f"fecha_limite: {fecha_limite}")
        print(f"ahora: {ahora}")
        print(f"ahora.date(): {ahora.date()}")
        print(f"Comparación ahora.date() >= fecha_entrada: {ahora.date() >= fecha_entrada}")
    
        
        # Solo mostrar indicadores para rentas ACTIVAS con fechas específicas
        if fecha_limite:
            fecha_limite_con_hora = datetime.combine(fecha_limite, datetime.strptime('10:00', '%H:%M').time())
            print(f"fecha_limite_con_hora: {fecha_limite_con_hora}")
            print(f"Comparación ahora > fecha_limite_con_hora: {ahora > fecha_limite_con_hora}")

            # Si ya pasó la fecha y hora límite = VENCIDA
            if ahora > fecha_limite_con_hora:
                print("🔴 ESTADO: VENCIDA")
                return {
                    'estado': 'vencida',
                    'clase': 'badge-vencida',
                    'texto': 'Vencida'
                }
            
            # Si llegó a la fecha de entrada pero no ha pasado la hora límite = POR REGRESAR
            elif ahora.date() >= fecha_entrada:
                print("🟡 ESTADO: POR REGRESAR")
                return {
                    'estado': 'por_regresar',
                    'clase': 'badge-por-regresar',
                    'texto': 'Por regresar'
                }
            else:
                print(f"⏳ Aún no llega la fecha. Hoy: {ahora.date()}, Fecha entrada: {fecha_entrada}")
        
        # En cualquier otro caso, no mostrar indicador adicional
        print("❌ No cumple condiciones para indicador")
        return None

    # Aplicar la función a todas las rentas
    rentas_con_estado = []
    for renta in rentas:
        estado_entrega = calcular_estado_entrega(renta)
        renta_lista = list(renta) + [estado_entrega]
        rentas_con_estado.append(renta_lista)

    cursor.close()
    conn.close()

    return render_template(
        'rentas/index.html',
        rentas=rentas_con_estado,
        clientes=clientes,
        productos=productos,
        productos_por_renta=productos_por_renta,
        sucursal_nombre=sucursal_nombre,
        precios_productos=precios_productos,
        sucursal_id=sucursal_id 
    )









@rentas_bp.route('/crear', methods=['POST'])
def crear_renta():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.form.get('renta_programada'):
            estado_renta = 'programada'
        else:
            estado_renta = 'en curso'
        estado_pago = 'Pago pendiente'
        metodo_pago = 'Pendiente'
        cliente_id = request.form['cliente_id']
        direccion_obra = request.form['direccion_obra']
        fecha_salida = request.form['fecha_salida']
        fecha_entrada = request.form.get('fecha_entrada') or None
        observaciones = request.form.get('observaciones')
        fecha_registro = datetime.now()
        fecha_programada = request.form.get('fecha_programada') or None
        costo_traslado = float(request.form.get('costo_traslado') or 0)
        traslado = request.form.get('traslado') or 'ninguno'
        id_sucursal = request.form.get('id_sucursal')
        
        print("ID SUCURSAL RECIBIDO EN CREAR:", id_sucursal)  # <-- Usar id_sucursal

        cursor.execute("""
                       
            INSERT INTO rentas (
                cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                direccion_obra, estado_renta, estado_pago, metodo_pago,
                total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                costo_traslado, traslado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente_id, fecha_registro, fecha_salida, fecha_entrada,
            direccion_obra, estado_renta, estado_pago, metodo_pago,
            0, 0, 0, observaciones, fecha_programada, id_sucursal,
            costo_traslado, traslado
        ))

        renta_id = cursor.lastrowid

        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')

        total = 0

        for i in range(len(productos)):
            prod_id = int(productos[i])
            cant = int(cantidades[i])
            dias_renta_raw = dias[i]
            if dias_renta_raw in (None, '', 'null'):
                dias_renta = None
                subtotal = 0
            else:
                dias_renta = int(dias_renta_raw)
                costo_unitario = float(costos[i])
                subtotal = cant * dias_renta * costo_unitario
                total += subtotal

            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                renta_id, prod_id, cant, dias_renta,
                float(costos[i]), subtotal
            ))

        # Calcular IVA y total con IVA
        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        cursor.execute("""
            UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
        """, (total, iva, total_con_iva, renta_id))

        conn.commit()
        flash("Renta registrada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al guardar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))


# Actualizar fecha de entrada de una renta
@rentas_bp.route('/actualizar_fecha_entrada/<int:renta_id>', methods=['POST'])
def actualizar_fecha_entrada(renta_id):
    try:
        nueva_fecha_str = request.json.get('fecha_entrada')
        if not nueva_fecha_str:
            return jsonify({'success': False, 'error': 'Fecha de entrada no proporcionada'}), 400

        # Parsear fecha_entrada enviada (asumiendo formato ISO YYYY-MM-DD)
        nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Obtener fecha_salida actual para calcular días
        cursor.execute("SELECT fecha_salida, costo_traslado FROM rentas WHERE id = %s", (renta_id,))
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'success': False, 'error': 'Renta no encontrada'}), 404

        fecha_salida = fila[0]
        costo_traslado = float(fila[1] or 0)

        if not fecha_salida:
            return jsonify({'success': False, 'error': 'Fecha de salida no definida'}), 400

        # Calcular días de renta
        dias_renta = (nueva_fecha - fecha_salida).days + 1
        if dias_renta < 1:
            dias_renta = 1

        # Actualizar fecha_entrada en rentas
        cursor.execute("UPDATE rentas SET fecha_entrada = %s WHERE id = %s", (nueva_fecha, renta_id))

        # Obtener detalles para actualizar días y subtotal
        cursor.execute("SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s", (renta_id,))
        detalles = cursor.fetchall()

        total = 0
        for detalle in detalles:
            detalle_id, cantidad, costo_unitario = detalle
            subtotal = cantidad * dias_renta * float(costo_unitario)
            cursor.execute("""
                UPDATE renta_detalle SET dias_renta = %s, subtotal = %s WHERE id = %s
            """, (dias_renta, subtotal, detalle_id))
            total += subtotal

        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        # Actualizar totales en rentas
        cursor.execute("""
            UPDATE rentas SET total = %s, iva = %s, total_con_iva = %s WHERE id = %s
        """, (total, iva, total_con_iva, renta_id))

        conn.commit()

        return jsonify({'success': True, 'message': 'Fecha de entrada y totales actualizados correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()




# Ejemplo de endpoint para cerrar renta y actualizar días/subtotales
@rentas_bp.route('/cerrar/<int:renta_id>', methods=['POST'])
def cerrar_renta(renta_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        fecha_entrada = request.form.get('fecha_entrada')
        if not fecha_entrada:
            flash("Debes ingresar la fecha de entrada para cerrar la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        # Obtener fecha_salida de la renta
        cursor.execute("SELECT fecha_salida FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        if not row:
            flash("Renta no encontrada.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))
        fecha_salida = row[0]

        # Calcular días de renta
        dias_renta = (datetime.strptime(fecha_entrada, "%Y-%m-%d") - datetime.strptime(str(fecha_salida), "%Y-%m-%d")).days + 1
        if dias_renta < 1:
            dias_renta = 1

        # Actualizar cada detalle de la renta
        cursor.execute("""
            SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        detalles = cursor.fetchall()
        for detalle in detalles:
            detalle_id, cantidad, costo_unitario = detalle
            subtotal = cantidad * dias_renta * costo_unitario
            cursor.execute("""
                UPDATE renta_detalle
                SET dias_renta = %s, subtotal = %s
                WHERE id = %s
            """, (dias_renta, subtotal, detalle_id))

        # Recalcular totales
        cursor.execute("""
            SELECT SUM(subtotal) FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        total = cursor.fetchone()[0] or 0

        # Obtener costo_traslado
        cursor.execute("SELECT costo_traslado FROM rentas WHERE id = %s", (renta_id,))
        costo_traslado = cursor.fetchone()[0] or 0

        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        cursor.execute("""
            UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s, estado_renta='cerrada'
            WHERE id=%s
        """, (fecha_entrada, total, iva, total_con_iva, renta_id))

        conn.commit()
        flash("Renta cerrada y actualizada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))




###################################
###################################
###################################
############## DETALLES DE LA RENTA - VISUALIZACIÓN DETALLES 

@rentas_bp.route('/detalle/<int:renta_id>')
def obtener_detalle_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Datos principales de la renta
        cursor.execute("""
            SELECT r.*, 
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.codigo_cliente, c.telefono, c.correo, c.rfc,
                   c.calle, c.numero_exterior, c.numero_interior, c.entre_calles,
                   c.colonia, c.codigo_postal, c.municipio, c.estado
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (renta_id,))
        renta = cursor.fetchone()
        
        if not renta:
            return jsonify({'error': 'Renta no encontrada'}), 404
        
        # Productos de la renta
        cursor.execute("""
            SELECT p.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
            FROM renta_detalle rd
            JOIN productos p ON rd.id_producto = p.id_producto
            WHERE rd.renta_id = %s
        """, (renta_id,))
        productos = cursor.fetchall()
        
        # Calcular fecha límite de entrega
        fecha_limite = "INDEFINIDA"
        if renta['fecha_entrada']:
            from datetime import timedelta
            fecha_limite_obj = renta['fecha_entrada'] + timedelta(days=1)
            fecha_limite = f"{fecha_limite_obj.strftime('%d/%m/%Y')} antes de las 9:00 a.m."
        
        # Formatear dirección completa del cliente
        direccion_cliente = renta['calle'] or ''
        if renta['numero_exterior']:
            direccion_cliente += f" #{renta['numero_exterior']}"
        if renta['numero_interior']:
            direccion_cliente += f", Int. {renta['numero_interior']}"
        if renta['entre_calles']:
            direccion_cliente += f" (entre {renta['entre_calles']})"
        if renta['colonia']:
            direccion_cliente += f", COL. {renta['colonia']}"
        if renta['codigo_postal']:
            direccion_cliente += f" - C.P. {renta['codigo_postal']}"
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'renta': {
                'id': renta['id'],
                'fecha_registro': renta['fecha_registro'].strftime('%d/%m/%Y %H:%M:%S'),
                'fecha_salida': renta['fecha_salida'].strftime('%d/%m/%Y') if renta['fecha_salida'] else 'No definida',
                'fecha_entrada': renta['fecha_entrada'].strftime('%d/%m/%Y') if renta['fecha_entrada'] else 'Indefinida',
                'estado_renta': renta['estado_renta'],
                'estado_pago': renta['estado_pago'],
                'metodo_pago': renta['metodo_pago'] or 'No definido',
                'direccion_obra': renta['direccion_obra'],
                'traslado': renta['traslado'] or 'Ninguno',
                'costo_traslado': float(renta['costo_traslado'] or 0),
                'iva': float(renta['iva'] or 0),
                'total': float(renta['total_con_iva'] or 0),
                'observaciones': renta['observaciones'],
                'fecha_limite': fecha_limite
            },
            'cliente': {
                'codigo': renta['codigo_cliente'],
                'nombre': renta['cliente_nombre'],
                'telefono': renta['telefono'] or 'No registrado',
                'email': renta['correo'] or 'No registrado',
                'rfc': renta['rfc'] or 'No registrado',
                'direccion': direccion_cliente
            },
            'productos': productos
        })
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500
