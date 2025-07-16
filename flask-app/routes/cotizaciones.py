from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from utils.db import get_db_connection
from datetime import datetime, timedelta
import json

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import send_file, current_app
from io import BytesIO
import os




cotizaciones_bp = Blueprint('cotizaciones', __name__, url_prefix='/cotizaciones')

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





def calcular_estado_vigencia(cotizacion):
    """Calcula el estado de vigencia de una cotización (similar a rentas)"""
    
    print(f"=== DEBUG COTIZACIÓN {cotizacion['id']} ===")
    print(f"estado: {cotizacion['estado']}")
    print(f"fecha_vigencia: {cotizacion['fecha_vigencia']} (tipo: {type(cotizacion['fecha_vigencia'])})")
    print(f"dias_para_vencer: {cotizacion['dias_para_vencer']}")
    
    # Solo mostrar indicadores para cotizaciones ENVIADAS
    if cotizacion['estado'] != 'enviada':
        print(f"❌ Estado no es 'enviada': {cotizacion['estado']}")
        return None
    
    # Si no tiene fecha de vigencia, no mostrar indicador
    if not cotizacion['fecha_vigencia']:
        print("❌ No tiene fecha de vigencia")
        return None
    
    print("✅ Pasó todas las validaciones!")
    
    fecha_vigencia = cotizacion['fecha_vigencia']
    dias_para_vencer = cotizacion['dias_para_vencer']
    ahora = datetime.now()
    
    print(f"fecha_vigencia: {fecha_vigencia}")
    print(f"dias_para_vencer: {dias_para_vencer}")
    print(f"ahora: {ahora}")
    print(f"ahora.date(): {ahora.date()}")
    
    # Si ya pasó la fecha de vigencia = VENCIDA
    if dias_para_vencer is not None and dias_para_vencer <= 0:
        print("🔴 ESTADO: VENCIDA")
        return {
            'estado': 'vencida',
            'clase': 'bg-danger',
            'texto': 'Vencida'
        }
    
    # Si le quedan 3 días o menos = POR VENCER
    elif dias_para_vencer is not None and dias_para_vencer <= 3:
        print("🟡 ESTADO: POR VENCER")
        return {
            'estado': 'por_vencer',
            'clase': 'bg-warning',
            'texto': f'Vence en {dias_para_vencer} día{"s" if dias_para_vencer != 1 else ""}'
        }
    
    # Si le quedan más de 3 días = VIGENTE
    elif dias_para_vencer is not None and dias_para_vencer > 3:
        print("🟢 ESTADO: VIGENTE")
        return {
            'estado': 'vigente',
            'clase': 'bg-success',
            'texto': f'{dias_para_vencer} días restantes'
        }
    
    # En cualquier otro caso, no mostrar indicador adicional
    print("❌ No cumple condiciones para indicador")
    return None





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












# En routes/cotizaciones.py, agregar estas funciones:

def generar_pdf_cotizacion_buffer(cotizacion_id):
    """Función auxiliar para generar PDF y retornar buffer"""
    import os
    
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    
    # Obtener datos de la cotización
    cursor.execute("""
        SELECT c.*, u.nombre as usuario_nombre, u.apellido1 as usuario_apellido,
               s.nombre as sucursal_nombre, s.direccion as sucursal_direccion
        FROM cotizaciones c
        JOIN usuarios u ON c.usuario_id = u.id
        JOIN sucursales s ON c.sucursal_id = s.id
        WHERE c.id = %s
    """, (cotizacion_id,))
    
    cotizacion = cursor.fetchone()
    
    # Obtener detalle de productos con piezas - CORREGIDO con JOIN a tabla piezas
    cursor.execute("""
        SELECT cd.*, p.nombre, p.descripcion, p.tipo, c.dias_renta,
               GROUP_CONCAT(DISTINCT CONCAT(pp.cantidad, ' ', pz.nombre_pieza) SEPARATOR ', ') as piezas
        FROM cotizacion_detalle cd
        JOIN productos p ON cd.producto_id = p.id_producto
        JOIN cotizaciones c ON cd.cotizacion_id = c.id
        LEFT JOIN producto_piezas pp ON p.id_producto = pp.id_producto
        LEFT JOIN piezas pz ON pp.id_pieza = pz.id_pieza
        WHERE cd.cotizacion_id = %s
        GROUP BY cd.id
    """, (cotizacion_id,))
    
    productos = cursor.fetchall()
    cursor.close()
    conexion.close()
    
    # --- GENERAR OVERLAY CON DATOS ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    # Registrar fuente Carlito
    try:
        pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))
        can.setFont("Carlito", 10)
    except:
        can.setFont("Carlito", 10)
    
    # === INFORMACIÓN DE LA EMPRESA (PARTE SUPERIOR) ===
    can.setFont("Helvetica-Bold", 12)
    can.drawString(50, 750, "COTIZACIÓN DE RENTA DE ANDAMIOS Y EQUIPO LIGERO")
    
    can.setFont("Carlito", 10)
    can.drawString(50, 735, f"Empresa: {cotizacion.get('sucursal_nombre', 'Tu Empresa')}")
    can.drawString(50, 720, f"Dirección: {cotizacion.get('sucursal_direccion', 'No disponible')}")
    can.drawString(50, 705, f"A {cotizacion.get('usuario_nombre', '')} {cotizacion.get('usuario_apellido', '')}")
    
    # Fecha y folio (lado derecho)
    # Una sola línea con formato completo
    can.drawString(482, 708, f"{cotizacion['fecha_creacion'].strftime('%d/%m/%Y - %H:%M:%S')}")
    can.setFont("Helvetica-Bold", 10)
    can.drawString(455, 665, f"COTIZACIÓN # {cotizacion['numero_cotizacion']}")
    can.setFont("Carlito", 10)
    can.drawString(455, 650, f"VIGENCIA: {cotizacion['fecha_vigencia'].strftime('%d/%m/%Y')}")
    
    # Línea separadora
    can.line(50, 600, 550, 600)
    
    # === DATOS DEL CLIENTE (TODOS DE LA TABLA COTIZACIONES) ===
    y = 600
    can.setFont("Helvetica-Bold", 11)
    can.drawString(50, y, "DATOS DEL CLIENTE")
    y -= 20
    
    can.setFont("Helvetica", 10)
    
    # Determinar destinatario (empresa o cliente)
    if cotizacion['cliente_empresa'] and cotizacion['cliente_empresa'].strip():
        destinatario = cotizacion['cliente_empresa']
        can.drawString(50, y, f"Empresa: {destinatario}")
        y -= 15
        can.drawString(50, y, f"Contacto: {cotizacion['cliente_nombre']}")
    else:
        destinatario = cotizacion['cliente_nombre']
        can.drawString(50, y, f"Cliente: {destinatario}")
    
    y -= 15
    can.drawString(50, y, f"Teléfono: {cotizacion['cliente_telefono']}")
    y -= 15
    can.drawString(50, y, f"Email: {cotizacion['cliente_email'] or 'No proporcionado'}")
    y -= 15
    can.drawString(50, y, f"Días de renta: {cotizacion['dias_renta']}")
    
    y -= 30
    
    # === SALUDO PERSONALIZADO ===
    can.setFont("Helvetica", 10)
    if cotizacion['cliente_empresa'] and cotizacion['cliente_empresa'].strip():
        saludo = f"Estimada empresa {cotizacion['cliente_empresa']}, se le presenta a continuación la siguiente cotización solicitada:"
    else:
        saludo = f"Estimado {cotizacion['cliente_nombre']}, se le presenta a continuación la siguiente cotización solicitada:"
    
    can.drawString(50, y, saludo)
    y -= 30
    
    # === TABLA DE PRODUCTOS ===
    can.setFont("Helvetica-Bold", 9)
    can.drawString(50, y, "PRODUCTO")
    can.drawString(250, y, "CANT.")
    can.drawString(300, y, "DÍAS")
    can.drawString(350, y, "PRECIO UNIT.")
    can.drawString(450, y, "SUBTOTAL")
    
    y -= 15
    can.line(50, y, 550, y)  # Línea separadora
    y -= 10
    
    can.setFont("Helvetica", 8)
    subtotal_productos = 0
    
    for producto in productos:
        # Nombre del producto
        can.drawString(50, y, producto['nombre'][:30])
        y -= 12
        
        # Descripción del producto (SIEMPRE se muestra)
        if producto['descripcion']:
            can.setFont("Helvetica", 7)
            can.drawString(55, y, f"{producto['descripcion'][:60]}")
            y -= 10
        
        # Piezas SOLO si es conjunto/kit Y tiene piezas
        if producto['tipo'] == 'conjunto' and producto['piezas']:
            can.setFont("Helvetica", 7)
            can.drawString(55, y, f"Incluye: {producto['piezas']}")
            y -= 10
        
        # Datos numéricos (cantidad, días, precios)
        can.setFont("Helvetica", 9)
        can.drawString(250, y + 10, str(producto['cantidad']))
        can.drawString(300, y + 10, str(producto['dias_renta']))
        can.drawString(350, y + 10, f"${producto['precio_unitario']:.2f}")
        can.drawString(450, y + 10, f"${producto['subtotal']:.2f}")
        
        subtotal_productos += producto['subtotal']
        y -= 15
    
    # Traslado si existe
    if cotizacion['requiere_traslado'] and cotizacion['costo_traslado'] > 0:
        can.setFont("Helvetica", 9)
        can.drawString(50, y, f"TRASLADO {cotizacion['tipo_traslado'].upper()}")
        y -= 10
        can.setFont("Helvetica", 7)
        can.drawString(55, y, "Servicio de transporte del equipo")
        y -= 5
        
        can.setFont("Helvetica", 9)
        can.drawString(250, y, "-")
        can.drawString(300, y, "-")
        can.drawString(350, y, f"${cotizacion['costo_traslado']:.2f}")
        can.drawString(450, y, f"${cotizacion['costo_traslado']:.2f}")
        y -= 20
    
    # Línea separadora antes de totales
    can.line(50, y, 550, y)
    y -= 20
    
    # === TOTALES ===
    can.setFont("Helvetica", 10)
    can.drawString(350, y, "SUBTOTAL:")
    can.drawString(450, y, f"${cotizacion['subtotal']:.2f}")
    y -= 15
    
    can.drawString(350, y, "IVA (16%):")
    can.drawString(450, y, f"${cotizacion['iva']:.2f}")
    y -= 15
    
    can.setFont("Helvetica-Bold", 11)
    can.drawString(350, y, "TOTAL:")
    can.drawString(450, y, f"${cotizacion['total']:.2f}")
    y -= 30
    
    # === CONDICIONES Y REQUISITOS ===
    can.setFont("Helvetica-Bold", 10)
    can.drawString(50, y, "REQUISITOS DEL CLIENTE:")
    y -= 15
    
    can.setFont("Helvetica", 8)
    requisitos = [
        "• Identificación oficial",
        "• Licencia de conducir", 
        "• Constancia de situación fiscal",
        "• Comprobante de domicilio"
    ]
    
    for req in requisitos:
        can.drawString(60, y, req)
        y -= 10
    
    y -= 10
    can.setFont("Helvetica-Bold", 10)
    can.drawString(50, y, "CONDICIONES:")
    y -= 15
    
    can.setFont("Helvetica", 8)
    condiciones = [
        "• Se requiere el pago completo por adelantado",
        "• Ubicación exacta de la obra (Google Maps)",
        "• El período incluye domingos y días festivos",
        "• No se arma, ni se desarma el equipo",
        "• Cotización válida por 7 días"
    ]
    
    for cond in condiciones:
        can.drawString(60, y, cond)
        y -= 10
    
    can.save()
    packet.seek(0)
    
    # --- COMBINAR CON PLANTILLA ---
    try:
        plantilla_path = os.path.join(current_app.root_path, 'static/notas/cotizacion.pdf')
        existing_pdf = PdfReader(plantilla_path)
        output = PdfWriter()
        
        # Leer el overlay
        new_pdf = PdfReader(packet)
        
        # Combinar con la plantilla
        page = existing_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        
    except Exception as e:
        print(f"Error al usar plantilla: {e}")
        # Si no hay plantilla, usar solo el overlay
        output = PdfWriter()
        new_pdf = PdfReader(packet)
        output.add_page(new_pdf.pages[0])
    
    # Retornar buffer
    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    
    return output_stream


# Mantener la función original para acceso directo
@cotizaciones_bp.route('/pdf/<int:cotizacion_id>')
def generar_pdf_cotizacion(cotizacion_id):
    """Generar PDF de cotización - acceso directo por URL"""
    try:
        buffer = generar_pdf_cotizacion_buffer(cotizacion_id)
        
        # Obtener número de cotización para el nombre del archivo
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT numero_cotizacion FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        cotizacion = cursor.fetchone()
        cursor.close()
        conexion.close()
        
        numero_cotizacion = cotizacion['numero_cotizacion'] if cotizacion else str(cotizacion_id)
        
        return send_file(
            buffer,
            download_name=f"cotizacion_{numero_cotizacion}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error al generar PDF: {e}")
        flash('Error al generar el PDF de la cotización', 'error')
        return redirect(url_for('cotizaciones.index'))














@cotizaciones_bp.route('/')
def index():
    """Página principal de cotizaciones"""
    try:
        verificar_cotizaciones_vencidas()
        
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        
        # Obtener filtros
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
        
        # Aplicar estado de vigencia
        cotizaciones_con_estado = []
        for cotizacion in cotizaciones:
            estado_vigencia = calcular_estado_vigencia(cotizacion)
            cotizacion_con_estado = dict(cotizacion)
            cotizacion_con_estado['estado_vigencia'] = estado_vigencia
            cotizaciones_con_estado.append(cotizacion_con_estado)
        
        # Obtener productos por cotización
        productos_por_cotizacion = {}
        for cotizacion in cotizaciones_con_estado:
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
                             cotizaciones=cotizaciones_con_estado,
                             productos_por_cotizacion=productos_por_cotizacion,
                             productos=productos_disponibles)
    
    except Exception as e:
        print(f"Error en cotizaciones index: {e}")
        flash('Error al cargar las cotizaciones', 'error')
        return render_template('cotizaciones/cotizacion.html', 
                             cotizaciones=[], 
                             productos_por_cotizacion={},
                             productos=[])









@cotizaciones_bp.route('/crear', methods=['POST'])
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
        
        # Obtener productos
        productos = []
        i = 0
        while f'productos[{i}][producto_id]' in request.form:
            producto_id = int(request.form[f'productos[{i}][producto_id]'])
            cantidad = int(request.form[f'productos[{i}][cantidad]'])
            precio_unitario = float(request.form[f'productos[{i}][precio_unitario]'])
            subtotal = float(request.form[f'productos[{i}][subtotal]'])
            
            productos.append({
                'producto_id': producto_id,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal
            })
            i += 1
        
        if not productos and not requiere_traslado:
            return jsonify({'error': 'Debe agregar al menos un producto o servicio de traslado'}), 400
        
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
        
        # Insertar cotización
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

        # Verificar si espera JSON o redirección
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'cotizacion_id': cotizacion_id,
                'pdf_url': url_for('cotizaciones.generar_pdf_cotizacion', cotizacion_id=cotizacion_id)
            })
        else:
            return redirect(url_for('cotizaciones.generar_pdf_cotizacion', cotizacion_id=cotizacion_id))
        
    except Exception as e:
        print(f"Error al crear cotización: {e}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'error': 'Error al crear la cotización'}), 500
        else:
            flash('Error al crear la cotización', 'error')
            return redirect(url_for('cotizaciones.index'))



        
        
        
 









@cotizaciones_bp.route('/precios/<int:producto_id>/<int:dias>')  # Cambiar de '/cotizaciones/precios/...' a '/precios/...'
def obtener_precio_producto(producto_id, dias):

    """API para obtener precio de producto según días"""
    try:
        precio = calcular_precio_por_dias(producto_id, dias)
        return jsonify({'precio': precio})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@cotizaciones_bp.route('/<int:cotizacion_id>/cambiar-estado', methods=['POST'])  # Quitar '/cotizaciones'
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




@cotizaciones_bp.route('/<int:cotizacion_id>/convertir-renta', methods=['POST'])  # Quitar '/cotizaciones'
def convertir_cotizacion_a_renta(cotizacion_id):
 
    """Convertir cotización a renta"""
    try:
        # Aquí implementarías la lógica para crear una renta basada en la cotización
        # Por ahora solo cambiamos el estado
        return cambiar_estado_cotizacion(cotizacion_id)
        
    except Exception as e:
        print(f"Error al convertir cotización a renta: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
    




















 