from flask import Blueprint, jsonify, redirect, request, send_file, current_app, url_for
from datetime import datetime, timedelta
from utils.db import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os

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
            VALUES (%s, %s, NOW() - INTERVAL 6 HOUR, %s, %s)
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
        return jsonify({'success': True, 'folio': folio, 'nota_salida_id': nota_salida_id})
    except Exception as e:
        conn.rollback()
        print(e)
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()









@notas_salida_bp.route('/pdf/<int:nota_salida_id>')
def generar_pdf_nota_salida(nota_salida_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos completos de la nota de salida
        cursor.execute("""
            SELECT ns.folio, ns.fecha, ns.numero_referencia, ns.observaciones,
                   r.fecha_salida, r.fecha_entrada, r.direccion_obra,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.codigo_cliente, c.telefono, c.calle, c.numero_exterior, 
                   c.numero_interior, c.entre_calles, c.colonia, c.codigo_postal
            FROM notas_salida ns
            JOIN rentas r ON ns.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE ns.id = %s
        """, (nota_salida_id,))
        nota = cursor.fetchone()
        
        if not nota:
            return "Nota de salida no encontrada", 404
        
        # Obtener piezas de la nota de salida
        cursor.execute("""
            SELECT nsd.cantidad, p.nombre_pieza
            FROM notas_salida_detalle nsd
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE nsd.nota_salida_id = %s
            ORDER BY p.nombre_pieza
        """, (nota_salida_id,))
        piezas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # --- GENERAR PDF COMPLETO ---
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))
        
        # CONFIGURACIÓN INICIAL
        page_width, page_height = letter
        y_position = page_height - 100  # Empezar desde arriba
        
        
        # Folio (esquina superior derecha)
        can.setFont("Carlito", 16)
        can.drawRightString(502,670, f"#{str(nota['folio']).zfill(5)}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 10)
        fecha_emision = nota['fecha'].strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(573, 708, f"{fecha_emision}")
        
        
        # === DATOS DEL CLIENTE ===
        
        # Cliente con código
        can.setFont("Carlito", 10)
        cliente_completo = f"{nota['codigo_cliente']} - {nota['cliente_nombre'].upper()}"
        can.drawString(62, 703, f"{cliente_completo}")
       
        
        # Teléfono
        can.drawString(69, 671, f"{nota['telefono'] or 'No registrado'}")
        
        
        # Número de referencia
        referencia = nota['numero_referencia'] or 'Sin número de referencia'
        can.drawString(231, 671, f"{referencia}")
        
        
        # Dirección completa
        direccion_completa = nota['calle'] or ''
        if nota['numero_exterior']:
            direccion_completa += f" #{nota['numero_exterior']}"
        if nota['numero_interior']:
            direccion_completa += f", Int. {nota['numero_interior']}"
        if nota['entre_calles']:
            direccion_completa += f" (entre {nota['entre_calles']})"
        if nota['colonia']:
            direccion_completa += f", COL. {nota['colonia']}"
        if nota['codigo_postal']:
            direccion_completa += f" - C.P. {nota['codigo_postal']}"
        
        can.drawString(73, 687, f"{direccion_completa.upper()}")
        
        
        # DATOS DE LA RENTA
        y_position -= 85
        # Datos de piezas
        can.setFont("Carlito", 10)
        for pieza in piezas:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                can.setFont("Carlito", 10)
                y_position = page_height - 60
            
            can.drawString(70, y_position+5, str(pieza['cantidad']))
            can.drawString(140, y_position+5, pieza['nombre_pieza'].upper())
            y_position -= 13
        
        y_position -= 5

        # Período de renta
        can.setFont("Carlito", 10)
        fecha_salida = nota['fecha_salida'].strftime('%d/%m/%Y') if nota['fecha_salida'] else 'No definida'
        if nota['fecha_entrada']:
            fecha_entrada = nota['fecha_entrada'].strftime('%d/%m/%Y')
            periodo = f"{fecha_salida} al {fecha_entrada}"
        else:
            periodo = f"{fecha_salida} a FECHA INDEFINIDA"
        
        can.drawString(60, y_position, f"PERIODO DE RENTA: {periodo}")
        y_position -= 15

        # Dirección de obra
                # Dirección de obra con saltos de línea automáticos
        can.setFont("Carlito", 10)
        direccion_obra_text = f"DIRECCIÓN DE OBRA: {nota['direccion_obra'].upper()}"

        # Función para dividir texto en líneas
        def dividir_texto_direccion(texto, max_chars=100):
            if len(texto) <= max_chars:
                return [texto]
            
            lineas = []
            palabras = texto.split(' ')
            linea_actual = ''
            
            for palabra in palabras:
                if len(linea_actual + ' ' + palabra) <= max_chars:
                    linea_actual = linea_actual + ' ' + palabra if linea_actual else palabra
                else:
                    if linea_actual:
                        lineas.append(linea_actual)
                    linea_actual = palabra
            
            if linea_actual:
                lineas.append(linea_actual)
            
            return lineas

        # Dividir la dirección de obra en líneas
        lineas_direccion = dividir_texto_direccion(direccion_obra_text, 100)

        # Dibujar cada línea
        for i, linea in enumerate(lineas_direccion):
            can.drawString(60, y_position, linea)
            y_position -= 12  # Espacio entre líneas

        y_position -= 3  # Espacio adicional después de la dirección

        # === FECHA LÍMITE DE ENTREGA ===
        can.setFont("Helvetica-Bold", 9)
        if nota['fecha_entrada']:
            fecha_limite_obj = nota['fecha_entrada'] + timedelta(days=1)
            fecha_limite = f"{fecha_limite_obj.strftime('%d/%m/%Y')} ANTES DE LAS 9:00 A.M."
            can.drawString(60, y_position, f"FECHA LÍMITE DE ENTREGA: {fecha_limite}")
        else:
            can.drawString(60, y_position, "FECHA LÍMITE DE ENTREGA: INDEFINIDA")

        y_position -= 30

        # Línea separadora
        can.line(30, y_position+24 , page_width - 30, y_position+24)
        
        y_position -= 15
        # === LEYENDA DE RESPONSABILIDAD ===
        can.setFont("Carlito", 11)
        can.drawString(60, y_position+24, "TÉRMINOS Y CONDICIONES")

        y_position += 20

        # Crear estilo para párrafos
        styles = getSampleStyleSheet()
        style_normal = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName='Carlito',
            fontSize=9,
            leading=11,
            leftIndent=0,
            rightIndent=0,
            spaceAfter=6,
        )

        # Texto completo como un solo párrafo con saltos de línea automáticos
        texto_completo = """

        POR MEDIO DE LA PRESENTE, RECONOZCO HABER RECIBIDO EN PERFECTO ESTADO Y FUNCIONANDO EL EQUIPO DESCRITO ANTERIORMENTE.<br/>
        ME COMPROMETO A:<br/>
        • HACER USO RESPONSABLE DEL EQUIPO RENTADO.<br/>
        • MANTENER EL EQUIPO EN LAS MISMAS CONDICIONES EN QUE FUE ENTREGADO.<br/>
        • DEVOLVER EL EQUIPO COMPLETO EN LA FECHA ACORDADA.<br/>
        • RESPONDER POR CUALQUIER DAÑO, PÉRDIDA O ROBO DEL EQUIPO DURANTE EL PERÍODO DE RENTA.<br/>
        • CUMPLIR CON TODAS LAS CONDICIONES ESTABLECIDAS EN EL CONTRATO DE RENTA.<br/><br/>

        <b>IMPORTANTE:</b> EN CASO DE NO DEVOLVER EL EQUIPO EN LA FECHA Y HORA LÍMITE ESTABLECIDA, ACEPTO QUE SE ME REALIZARÁ EL CARGO DE COBRO CORRESPONDIENTE POR DÍA DE RETRASO;
          EL COBRO SE CALCULARÁ CON BASE EN LA TARIFA DIARIA ORIGINAL DE LA RENTA.<br/><br/>

        LA EMPRESA SE DESLINDA DE CUALQUIER RESPONSABILIDAD POR ACCIDENTES O DAÑOS CAUSADOS POR EL MAL USO DEL EQUIPO. EL CLIENTE ASUME TODA RESPONSABILIDAD DURANTE EL PERÍODO DE RENTA.
        """

        # Crear y dibujar el párrafo
        p = Paragraph(texto_completo, style_normal)
        ancho_disponible = page_width - 120  # Margen de 60 píxeles a cada lado
        alto_disponible = y_position - 150

        # Verificar si necesitamos nueva página
        if y_position < 200:
            can.showPage()
            y_position = page_height - 60
            alto_disponible = y_position - 150

        w, h = p.wrap(ancho_disponible, alto_disponible)
        p.drawOn(can, 60, y_position - h)

        y_position -= h + 20
        

        # === FIRMAS ===
        if y_position < 120:
            can.showPage()
            y_position = page_height - 200
        
        y_position -= 30
        # Líneas para firmas
        can.setFont("Carlito", 10)
        can.line(60, y_position, 250, y_position)  # Línea cliente
        can.line(350, y_position, 540, y_position)  # Línea empresa
        
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, "FIRMA DEL LA EMPRESA")
        can.drawString(350, y_position, "FIRMA DEL CLIENTE")
        
        y_position -= 20
        can.drawString(60, y_position, "ENTREGA: ________________________")
        can.drawString(350, y_position, "RECIBE: ________________________")
        
        # Observaciones si existen
        if nota['observaciones']:
            y_position -= 40
            can.setFont("Carlito", 10)
            can.drawString(60, y_position, "OBSERVACIONES:")
            y_position -= 12
            can.setFont("Carlito", 9)
            can.drawString(60, y_position, nota['observaciones'])
        
        # Guardar el canvas
        can.save()
        packet.seek(0)
        
        # --- COMBINAR CON LA PLANTILLA ---
        try:
            plantilla_path = os.path.join(current_app.root_path, 'static/notas/salida_plantilla.pdf')
            if os.path.exists(plantilla_path):
                plantilla_pdf = PdfReader(plantilla_path)
                overlay_pdf = PdfReader(packet)
                output = PdfWriter()
                
                page = plantilla_pdf.pages[0]
                page.merge_page(overlay_pdf.pages[0])
                output.add_page(page)
            else:
                # Si no hay plantilla, usar solo el overlay
                overlay_pdf = PdfReader(packet)
                output = PdfWriter()
                output.add_page(overlay_pdf.pages[0])
        except Exception as e:
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            output.add_page(overlay_pdf.pages[0])
        
        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)
        
        return send_file(
            output_stream, 
            download_name=f"nota_salida_{str(nota['folio']).zfill(5)}.pdf", 
            mimetype='application/pdf'
        )
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return f"Error al generar PDF: {str(e)}", 500
    
@notas_salida_bp.route('/pdf_renta/<int:renta_id>')
def generar_pdf_nota_salida_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM notas_salida 
        WHERE renta_id = %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (renta_id,))
    
    nota = cursor.fetchone()
    cursor.close()
    conn.close()

    if not nota:
        return f"No hay nota de salida para la renta {renta_id}", 404

    return redirect(url_for('notas_salida.generar_pdf_nota_salida', nota_salida_id=nota['id']))