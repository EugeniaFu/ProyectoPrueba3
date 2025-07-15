from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from utils.db import get_db_connection
from datetime import datetime, timedelta
import json

cotizaciones_bp = Blueprint('cotizaciones', __name__)

# Definir los estados de cotización
ESTADOS_COTIZACION = {
    'ENVIADA': 'enviada',
    'VENCIDA': 'vencida',
    'RENTA': 'renta'
}

def generar_numero_cotizacion():
    """Genera un número único de cotización"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    # Obtener el año actual
    año_actual = datetime.now().year
    
    # Buscar el último número de cotización del año
    cursor.execute("""
        SELECT numero_cotizacion 
        FROM cotizaciones 
        WHERE numero_cotizacion LIKE %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (f"{año_actual}%",))
    
    resultado = cursor.fetchone()
    
    if resultado:
        ultimo_numero = int(resultado[0].split('-')[1])
        nuevo_numero = ultimo_numero + 1
    else:
        nuevo_numero = 1
    
    cursor.close()
    conexion.close()
    
    return f"{año_actual}-{nuevo_numero:04d}"

def verificar_cotizaciones_vencidas():
    """Actualiza automáticamente las cotizaciones vencidas"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    try:
        # Marcar como vencidas las cotizaciones que pasaron los 7 días
        cursor.execute("""
            UPDATE cotizaciones 
            SET estado = 'vencida' 
            WHERE estado = 'enviada' 
            AND fecha_vigencia < CURDATE()
        """)
        
        conexion.commit()
        print(f"Cotizaciones vencidas actualizadas: {cursor.rowcount}")
        
    except Exception as e:
        print(f"Error al actualizar cotizaciones vencidas: {e}")
        conexion.rollback()
    finally:
        cursor.close()
        conexion.close()

def calcular_precio_por_dias(producto_id, dias_renta):
    """Calcula el precio según los días de renta"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    cursor.execute("""
        SELECT precio_dia, precio_7dias, precio_15dias, precio_30dias, precio_31mas
        FROM producto_precios 
        WHERE id_producto = %s
    """, (producto_id,))
    
    precios = cursor.fetchone()
    cursor.close()
    conexion.close()
    
    if not precios:
        return 0.00
    
    # Lógica para determinar precio según días
    if dias_renta <= 6:
        return float(precios[0])  # precio_dia
    elif dias_renta <= 14:
        return float(precios[1])  # precio_7dias
    elif dias_renta <= 29:
        return float(precios[2])  # precio_15dias
    elif dias_renta == 30:
        return float(precios[3])  # precio_30dias
    else:
        return float(precios[4])  # precio_31mas






@cotizaciones_bp.route('/cotizaciones')
def index():
    """Página principal de cotizaciones"""
    try:
        # Verificar cotizaciones vencidas antes de mostrar
        verificar_cotizaciones_vencidas()
        
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        
        # Obtener filtros de búsqueda
        busqueda = request.args.get('busqueda', '')
        filtro_estado = request.args.get('filtro', '')
        
        # Query base
        query = """
            SELECT c.*, u.nombre as usuario_nombre, u.apellido1 as usuario_apellido,
                   s.nombre as sucursal_nombre,
                   DATEDIFF(c.fecha_vigencia, CURDATE()) as dias_para_vencer
            FROM cotizaciones c
            JOIN usuarios u ON c.usuario_id = u.id
            JOIN sucursales s ON c.sucursal_id = s.id
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if busqueda:
            query += " AND (c.numero_cotizacion LIKE %s OR c.cliente_nombre LIKE %s OR c.cliente_empresa LIKE %s)"
            busqueda_param = f"%{busqueda}%"
            params.extend([busqueda_param, busqueda_param, busqueda_param])
        
        if filtro_estado:
            query += " AND c.estado = %s"
            params.append(filtro_estado)
        
        query += " ORDER BY c.fecha_creacion DESC"
        
        cursor.execute(query, params)
        cotizaciones = cursor.fetchall()
        
        # Obtener productos por cotización
        productos_por_cotizacion = {}
        for cotizacion in cotizaciones:
            cursor.execute("""
                SELECT p.nombre, cd.cantidad, cd.precio_unitario, cd.subtotal
                FROM cotizacion_detalle cd
                JOIN productos p ON cd.producto_id = p.id_producto
                WHERE cd.cotizacion_id = %s
            """, (cotizacion['id'],))
            productos_por_cotizacion[cotizacion['id']] = cursor.fetchall()
        
        # Obtener productos para el modal
        cursor.execute("SELECT id_producto, nombre FROM productos WHERE estatus = 'activo'")
        productos_disponibles = cursor.fetchall()
        
        cursor.close()
        conexion.close()
        
        return render_template('cotizaciones/cotizacion.html', 
                             cotizaciones=cotizaciones,
                             productos_por_cotizacion=productos_por_cotizacion,
                             productos=productos_disponibles)
    
    except Exception as e:
        print(f"Error en cotizaciones index: {e}")
        flash('Error al cargar las cotizaciones', 'error')
        return render_template('cotizaciones/cotizacion.html', 
                             cotizaciones=[], 
                             productos_por_cotizacion={},
                             productos=[])






@cotizaciones_bp.route('/cotizaciones/crear', methods=['POST'])
def crear_cotizacion():
    """Crear nueva cotización"""
    try:
        # Obtener datos del formulario
        cliente_nombre = request.form.get('cliente_nombre')
        cliente_telefono = request.form.get('cliente_telefono')
        cliente_email = request.form.get('cliente_email', '')
        cliente_empresa = request.form.get('cliente_empresa', '')
        dias_renta = int(request.form.get('dias_renta'))
        requiere_traslado = bool(request.form.get('requiere_traslado'))
        tipo_traslado = request.form.get('tipo_traslado') if requiere_traslado else None
        costo_traslado = float(request.form.get('costo_traslado', 0)) if requiere_traslado else 0
        
        # Calcular fecha de vigencia: 7 días desde hoy
        fecha_vigencia = datetime.now() + timedelta(days=7)
        
        # Obtener productos (formato: productos[0][campo])
        productos = []
        i = 0
        while f'productos[{i}][producto_id]' in request.form:
            if request.form.get(f'productos[{i}][producto_id]'):
                producto_id = int(request.form.get(f'productos[{i}][producto_id]'))
                cantidad = int(request.form.get(f'productos[{i}][cantidad]'))
                precio_unitario = float(request.form.get(f'productos[{i}][precio_unitario]'))
                
                # Calcular subtotal: precio × cantidad × días
                subtotal = precio_unitario * cantidad * dias_renta
                
                producto = {
                    'producto_id': producto_id,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal
                }
                productos.append(producto)
            i += 1
        
        if not productos and not requiere_traslado:
            flash('Debe agregar al menos un producto o servicio', 'error')
            return redirect(url_for('cotizaciones.index'))
        
        # Calcular totales
        subtotal_productos = sum(p['subtotal'] for p in productos)
        subtotal_total = subtotal_productos + costo_traslado
        iva = subtotal_total * 0.16
        total = subtotal_total + iva
        
        # Generar número de cotización
        numero_cotizacion = generar_numero_cotizacion()
        
        # Obtener usuario y sucursal de la sesión
        usuario_id = session.get('user_id')
        sucursal_id = session.get('sucursal_id')
        
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Insertar cotización con estado 'enviada'
        cursor.execute("""
            INSERT INTO cotizaciones (
                numero_cotizacion, cliente_nombre, cliente_telefono, cliente_email,
                cliente_empresa, dias_renta, requiere_traslado, tipo_traslado,
                costo_traslado, subtotal, iva, total, fecha_vigencia, estado, usuario_id, sucursal_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_cotizacion, cliente_nombre, cliente_telefono, cliente_email,
            cliente_empresa, dias_renta, requiere_traslado, tipo_traslado,
            costo_traslado, subtotal_total, iva, total, fecha_vigencia.date(), 
            'enviada', usuario_id, sucursal_id
        ))
        
        cotizacion_id = cursor.lastrowid
        
        # Insertar detalle de productos
        for producto in productos:
            cursor.execute("""
                INSERT INTO cotizacion_detalle (
                    cotizacion_id, producto_id, cantidad, precio_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                cotizacion_id, producto['producto_id'], producto['cantidad'],
                producto['precio_unitario'], producto['subtotal']
            ))
        
        # Insertar seguimiento
        cursor.execute("""
            INSERT INTO cotizacion_seguimiento (
                cotizacion_id, estado_nuevo, comentarios, usuario_id
            ) VALUES (%s, %s, %s, %s)
        """, (cotizacion_id, 'enviada', 'Cotización creada y enviada', usuario_id))
        
        conexion.commit()
        cursor.close()
        conexion.close()
        
        flash(f'Cotización {numero_cotizacion} creada y enviada exitosamente (válida hasta {fecha_vigencia.strftime("%d/%m/%Y")})', 'success')
        return redirect(url_for('cotizaciones.index'))
        
    except Exception as e:
        print(f"Error al crear cotización: {e}")
        flash('Error al crear la cotización', 'error')
        return redirect(url_for('cotizaciones.index'))





@cotizaciones_bp.route('/cotizaciones/precios/<int:producto_id>/<int:dias>')
def obtener_precio_producto(producto_id, dias):
    """API para obtener precio de producto según días"""
    try:
        precio = calcular_precio_por_dias(producto_id, dias)
        return jsonify({'precio': precio})
    except Exception as e:
        return jsonify({'error': str(e)}), 500






@cotizaciones_bp.route('/cotizaciones/<int:cotizacion_id>/cambiar-estado', methods=['POST'])
def cambiar_estado_cotizacion(cotizacion_id):
    """Cambiar estado de una cotización"""
    try:
        nuevo_estado = request.json.get('estado')
        comentarios = request.json.get('comentarios', '')
        usuario_id = session.get('user_id')
        
        # Validar que el estado sea válido
        if nuevo_estado not in ['enviada', 'vencida', 'renta']:
            return jsonify({'error': 'Estado no válido'}), 400
        
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Obtener estado actual
        cursor.execute("SELECT estado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return jsonify({'error': 'Cotización no encontrada'}), 404
        
        estado_anterior = resultado[0]
        
        # Actualizar estado
        cursor.execute("""
            UPDATE cotizaciones 
            SET estado = %s 
            WHERE id = %s
        """, (nuevo_estado, cotizacion_id))
        
        # Registrar seguimiento
        cursor.execute("""
            INSERT INTO cotizacion_seguimiento (
                cotizacion_id, estado_anterior, estado_nuevo, comentarios, usuario_id
            ) VALUES (%s, %s, %s, %s, %s)
        """, (cotizacion_id, estado_anterior, nuevo_estado, comentarios, usuario_id))
        
        conexion.commit()
        cursor.close()
        conexion.close()
        
        return jsonify({'success': True, 'message': 'Estado actualizado correctamente'})
        
    except Exception as e:
        print(f"Error al cambiar estado: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500







@cotizaciones_bp.route('/cotizaciones/<int:cotizacion_id>/convertir-renta', methods=['POST'])
def convertir_cotizacion_a_renta(cotizacion_id):
    """Convertir cotización a renta"""
    try:
        # Aquí implementarías la lógica para crear una renta basada en la cotización
        # Por ahora solo cambiamos el estado
        return cambiar_estado_cotizacion(cotizacion_id)
        
    except Exception as e:
        print(f"Error al convertir cotización a renta: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500