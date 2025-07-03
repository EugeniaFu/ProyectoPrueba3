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

notas_entrada_bp = Blueprint('notas_entrada', __name__, url_prefix='/notas_entrada')

@notas_entrada_bp.route('/preview/<int:renta_id>')
def preview_nota_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Siguiente folio
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_entrada")
        folio = str(cursor.fetchone()['siguiente_folio']).zfill(5)

        # 2. Datos de la renta y cliente
        cursor.execute("""
            SELECT r.fecha_salida, r.fecha_entrada, r.direccion_obra,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.telefono
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (renta_id,))
        renta = cursor.fetchone()
        
        if not renta:
            return jsonify({'error': 'Renta no encontrada'}), 404

        # 3. Obtener piezas que salieron (de la nota de salida)
        cursor.execute("""
            SELECT nsd.id_pieza, p.nombre_pieza, nsd.cantidad
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE ns.renta_id = %s
        """, (renta_id,))
        piezas_salida = cursor.fetchall()

        # 4. Calcular si hay retraso
        fecha_limite = None
        hay_retraso = False
        cobro_retraso = 0
        
        if renta['fecha_entrada']:  # Renta con fecha definida
            fecha_limite = datetime.combine(renta['fecha_entrada'] + timedelta(days=1), datetime.min.time().replace(hour=10))
            if datetime.now() > fecha_limite:
                hay_retraso = True
                dias_retraso = (datetime.now().date() - (renta['fecha_entrada'] + timedelta(days=1))).days + 1
                cobro_retraso = dias_retraso * 100  # $100 por día de retraso
        else:  # Renta indefinida
            fecha_limite = "Indefinida - se cobrará desde hoy"

        cursor.close()
        conn.close()

        return jsonify({
            'folio': folio,
            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'cliente': renta['cliente_nombre'],
            'telefono': renta['telefono'],
            'direccion_obra': renta['direccion_obra'],
            'fecha_entrada_original': renta['fecha_entrada'].strftime('%d/%m/%Y') if renta['fecha_entrada'] else 'Indefinida',
            'fecha_limite': fecha_limite.strftime('%d/%m/%Y %H:%M') if isinstance(fecha_limite, datetime) else str(fecha_limite),
            'hay_retraso': hay_retraso,
            'cobro_retraso': cobro_retraso,
            'piezas': piezas_salida
        })
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500

@notas_entrada_bp.route('/crear/<int:renta_id>', methods=['POST'])
def crear_nota_entrada(renta_id):
    data = request.get_json()
    fecha_entrada_real = data.get('fecha_entrada_real')  # Para rentas indefinidas
    observaciones = data.get('observaciones')
    piezas = data.get('piezas', [])
    cobro_adicional = float(data.get('cobro_adicional', 0))
    motivo_cobro = data.get('motivo_cobro')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener siguiente folio
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_entrada")
        folio = cursor.fetchone()['siguiente_folio']

        # Determinar estado de la nota
        estado = 'completada'
        for pieza in piezas:
            if pieza.get('estado_pieza') == 'dañada' or pieza.get('costo_daño', 0) > 0:
                estado = 'con_daños'
                break
        
        if cobro_adicional > 0:
            estado = 'con_retraso' if 'retraso' in motivo_cobro.lower() else 'con_daños'

        # Insertar nota de entrada
        cursor.execute("""
            INSERT INTO notas_entrada (
                folio, renta_id, fecha, fecha_entrada_real, observaciones, 
                cobro_adicional, motivo_cobro, estado
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
        """, (folio, renta_id, fecha_entrada_real, observaciones, cobro_adicional, motivo_cobro, estado))
        nota_entrada_id = cursor.lastrowid

        # Obtener la sucursal de la renta
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        id_sucursal = row['id_sucursal'] if row else None

        # Insertar detalle de piezas y actualizar inventario
        for pieza in piezas:
            id_pieza = pieza.get('id_pieza')
            cantidad_esperada = pieza.get('cantidad_esperada')
            cantidad_recibida = pieza.get('cantidad_recibida', cantidad_esperada)
            estado_pieza = pieza.get('estado_pieza', 'buena')
            costo_daño = float(pieza.get('costo_daño', 0))
            obs_pieza = pieza.get('observaciones', '')

            if id_pieza and cantidad_esperada:
                # Insertar detalle
                cursor.execute("""
                    INSERT INTO notas_entrada_detalle (
                        nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                        estado_pieza, costo_daño, observaciones
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida, 
                      estado_pieza, costo_daño, obs_pieza))

                # Actualizar inventario: regresar piezas que están en buen estado
                if estado_pieza == 'buena':
                    cursor.execute("""
                        UPDATE inventario_sucursal
                        SET disponibles = disponibles + %s,
                            rentadas = rentadas - %s
                        WHERE id_sucursal = %s AND id_pieza = %s
                    """, (cantidad_recibida, cantidad_recibida, id_sucursal, id_pieza))

        # Actualizar estado de la renta a "finalizada"
        cursor.execute("""
            UPDATE rentas SET estado_renta = 'finalizada', fecha_entrada = %s WHERE id = %s
        """, (fecha_entrada_real or datetime.now().date(), renta_id))

        conn.commit()
        return jsonify({'success': True, 'folio': folio, 'nota_entrada_id': nota_entrada_id})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()

@notas_entrada_bp.route('/pdf/<int:nota_entrada_id>')
def generar_pdf_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos de la nota de entrada
        cursor.execute("""
            SELECT ne.folio, ne.fecha, ne.fecha_entrada_real, ne.observaciones,
                   ne.cobro_adicional, ne.motivo_cobro, ne.estado,
                   r.fecha_salida, r.fecha_entrada, r.direccion_obra,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.telefono AS celular
            FROM notas_entrada ne
            JOIN rentas r ON ne.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE ne.id = %s
        """, (nota_entrada_id,))
        nota = cursor.fetchone()
        
        if not nota:
            return "Nota de entrada no encontrada", 404
        
        # Obtener piezas de la nota de entrada
        cursor.execute("""
            SELECT ned.cantidad_esperada, ned.cantidad_recibida, ned.estado_pieza, 
                   ned.costo_daño, ned.observaciones as obs_pieza, p.nombre_pieza
            FROM notas_entrada_detalle ned
            JOIN piezas p ON ned.id_pieza = p.id_pieza
            WHERE ned.nota_entrada_id = %s
        """, (nota_entrada_id,))
        piezas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # --- GENERAR PDF (similar a nota de salida, ajustado para entrada) ---
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))
        
        # Aquí agregarías todo el código para dibujar el PDF con los datos de entrada
        # Similar al de nota de salida pero con campos específicos de entrada
        
        can.save()
        packet.seek(0)
        
        # Usar plantilla de entrada
        plantilla_path = os.path.join(current_app.root_path, 'static/notas/plantilla_entrada.pdf')
        plantilla_pdf = PdfReader(plantilla_path)
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        
        page = plantilla_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        output.add_page(page)
        
        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)
        
        return send_file(output_stream, download_name=f"nota_entrada_{str(nota['folio']).zfill(5)}.pdf", mimetype='application/pdf')
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return f"Error al generar PDF: {str(e)}", 500