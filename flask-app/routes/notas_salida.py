from flask import Blueprint, jsonify, request, send_file, current_app
from datetime import datetime, timedelta
from utils.db import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
        # Obtener datos de la nota de salida
        cursor.execute("""
            SELECT ns.folio, ns.fecha, ns.numero_referencia, ns.observaciones,
                   r.fecha_salida, r.fecha_entrada, r.direccion_obra,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.telefono AS celular
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
        """, (nota_salida_id,))
        piezas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # --- GENERAR OVERLAY CON DATOS ---
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))
        
        # Configurar fuente
        can.setFont("Carlito", 13)
        
        # FOLIO (esquina superior derecha)
        can.setFont("Carlito", 15)
        can.drawString(450, 704, f"# {str(nota['folio']).zfill(5)}")
        
        # FECHA Y HORA DE EMISIÓN
        can.setFont("Carlito", 13)
        fecha_emision = nota['fecha'].strftime('%d/%m/%Y %H:%M')
        can.drawString(408, 682, fecha_emision)
        
        # DATOS DEL CLIENTE
        can.setFont("Carlito", 13)
        can.drawString(65, 709, nota['cliente_nombre'])  # NOMBRE
        can.drawString(63, 693, nota['celular'])         # CELULAR
        can.drawString(193, 693, nota['numero_referencia'] or 'Sin referencia')  # NÚMERO DE REFERENCIA
        
        # DIRECCIÓN DE OBRA (con ajuste automático de líneas)
        can.setFont("Carlito", 13)
        direccion = nota['direccion_obra']
        
        # Función para dividir texto en líneas
        def dividir_texto(texto, max_chars=60):
            """Divide el texto en líneas de máximo max_chars caracteres"""
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
        
        # Dividir la dirección en líneas y dibujarlas
        lineas_direccion = dividir_texto(direccion, 100)  # Máximo 60 caracteres por línea
        y_direccion = 523
        for i, linea in enumerate(lineas_direccion[:2]):  # Máximo 2 líneas
            can.drawString(50, y_direccion - (i * 12), linea)
        
        # PERIODO DE RENTA
        fecha_salida = nota['fecha_salida'].strftime('%d/%m/%Y') if nota['fecha_salida'] else '--/--/----'
        if nota['fecha_entrada']:
            fecha_entrada = nota['fecha_entrada'].strftime('%d/%m/%Y')
            periodo = f"{fecha_salida} - {fecha_entrada}"
            # Fecha de entrega (día posterior a fecha_entrada)
            fecha_entrega = (nota['fecha_entrada'] + timedelta(days=1)).strftime('%d/%m/%Y')
        else:
            periodo = f"{fecha_salida} - INDEFINIDA"
            fecha_entrega = "INDEFINIDA"
        
        can.setFont("Carlito", 12)
        can.drawString(107, 502, periodo)  # PERIODO

        can.setFont("Carlito", 12)
        can.drawString(325, 432, f" {fecha_entrega}")  # FECHA DE ENTREGA
        
        # TABLA DE PIEZAS
        y = 634
        can.setFont("Carlito", 12)
        
        # Determinar qué plantilla usar basado en el número de piezas
        usar_plantilla_extendida = len(piezas) > 6
        
        if usar_plantilla_extendida:
            # Plantilla extendida: dos columnas
            columna_izq = piezas[:len(piezas)//2 + len(piezas)%2]  # Primera mitad (más uno si es impar)
            columna_der = piezas[len(piezas)//2 + len(piezas)%2:]  # Segunda mitad
            
            # Columna izquierda
            y_izq = 630
            for pieza in columna_izq:
                can.drawString(110, y_izq, pieza['nombre_pieza'])  # NOMBRE DE PIEZA
                can.drawRightString(65, y_izq, str(pieza['cantidad']))  # CANTIDAD
                y_izq -= 15
            
            # Columna derecha
            y_der = 630
            for pieza in columna_der:
                can.drawString(398, y_der, pieza['nombre_pieza'])  # NOMBRE DE PIEZA (columna derecha)
                can.drawRightString(335, y_der, str(pieza['cantidad']))  # CANTIDAD (columna derecha)
                y_der -= 14
        else:
            # Plantilla normal: una columna (máximo 5 piezas)
            for pieza in piezas[:5]:  # Limitar a 5 piezas en plantilla normal
                can.drawString(125, y, pieza['nombre_pieza'])  # NOMBRE DE PIEZA
                can.drawRightString(65, y, str(pieza['cantidad']))  # CANTIDAD
                y -= 14
        
        # Guardar el canvas
        can.save()
        packet.seek(0)
        
        # --- COMBINAR CON LA PLANTILLA ---
        # Seleccionar plantilla según número de piezas
        if usar_plantilla_extendida:
            plantilla_filename = 'plantilla_salida_extendida.pdf'
        else:
            plantilla_filename = 'plantilla_salida.pdf'
            
        plantilla_path = os.path.join(current_app.root_path, f'static/notas/{plantilla_filename}')
        plantilla_pdf = PdfReader(plantilla_path)
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        
        page = plantilla_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        output.add_page(page)
        
        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)
        
        return send_file(output_stream, download_name=f"nota_salida_{str(nota['folio']).zfill(5)}.pdf", mimetype='application/pdf')
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return f"Error al generar PDF: {str(e)}", 500