from flask import Blueprint, jsonify, redirect, render_template, request, send_file, current_app, url_for
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

# === VISTA PREVIA NOTA DE ENTRADA ===
@notas_entrada_bp.route('/preview/<int:renta_id>')
def preview_nota_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_entrada")
        folio = str(cursor.fetchone()['siguiente_folio']).zfill(5)

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

        cursor.execute("""
            SELECT nsd.id_pieza, p.nombre_pieza, nsd.cantidad
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE ns.renta_id = %s
        """, (renta_id,))
        piezas_salida = cursor.fetchall()

        fecha_limite = None
        hay_retraso = False
        cobro_retraso = 0
        
        if renta['fecha_entrada']:
            fecha_limite = datetime.combine(renta['fecha_entrada'] + timedelta(days=1), datetime.min.time().replace(hour=10))
            if datetime.now() > fecha_limite:
                hay_retraso = True
                dias_retraso = (datetime.now().date() - (renta['fecha_entrada'] + timedelta(days=1))).days + 1
                cobro_retraso = dias_retraso * 100
        else:
            fecha_limite = "Indefinida - se cobrará desde hoy"

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
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# === CREAR NOTA DE ENTRADA ===
@notas_entrada_bp.route('/crear/<int:renta_id>', methods=['POST'])
def crear_nota_entrada(renta_id):
    data = request.get_json()
    fecha_entrada_real = data.get('fecha_entrada_real')
    observaciones = data.get('observaciones')
    piezas = data.get('piezas', [])
    cobro_adicional = float(data.get('cobro_adicional', 0))
    motivo_cobro = data.get('motivo_cobro')
    usuario_id = 1  # Placeholder o traer de sesión

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_entrada")
        folio = cursor.fetchone()['siguiente_folio']

        estado = 'completada'
        for pieza in piezas:
            if pieza.get('estado_pieza') == 'dañada' or pieza.get('costo_daño', 0) > 0:
                estado = 'con_daños'
                break
        if cobro_adicional > 0:
            estado = 'con_retraso' if 'retraso' in motivo_cobro.lower() else 'con_daños'
        
        if cobro_adicional > 0:
            cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_costo_extra")
            folio_extra = str(cursor.fetchone()['siguiente_folio']).zfill(5)

            cursor.execute("""
                INSERT INTO notas_costo_extra (
                    renta_id, nota_entrada_id, folio, monto, motivo, usuario_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (renta_id, nota_entrada_id, folio_extra, cobro_adicional, motivo_cobro, usuario_id))

            nota_extra_id = cursor.lastrowid
            pdf_extra_url = f"/notas_entrada/pdf_costo_extra/{nota_extra_id}"

            cursor.execute("UPDATE notas_costo_extra SET pdf_url = %s WHERE id = %s", (pdf_extra_url, nota_extra_id))

        cursor.execute("""
            INSERT INTO notas_entrada (
                folio, renta_id, fecha, fecha_entrada_real, observaciones, 
                usuario_id, cobro_adicional, motivo_cobro, estado
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
        """, (folio, renta_id, fecha_entrada_real, observaciones,
              usuario_id, cobro_adicional, motivo_cobro, estado))
        nota_entrada_id = cursor.lastrowid

        # === Generar y guardar la URL del PDF ===
        pdf_url = f"/notas_entrada/pdf/{nota_entrada_id}"

        cursor.execute("""
            UPDATE notas_entrada SET pdf_url = %s WHERE id = %s
        """, (pdf_url, nota_entrada_id))

        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        id_sucursal = cursor.fetchone()['id_sucursal']

        for pieza in piezas:
            id_pieza = pieza['id_pieza']
            cantidad_esperada = pieza['cantidad_esperada']
            cantidad_recibida = pieza.get('cantidad_recibida', cantidad_esperada)
            estado_pieza = pieza.get('estado_pieza', 'buena')
            costo_daño = float(pieza.get('costo_daño', 0))
            obs_pieza = pieza.get('observaciones', '')

            # Insertar detalle de la nota de entrada
            cursor.execute("""
                INSERT INTO notas_entrada_detalle (
                    nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                    estado_pieza, costo_daño, observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                estado_pieza, costo_daño, obs_pieza))

            # ACTUALIZAR INVENTARIO SEGÚN ESTADO DE LA PIEZA
            if estado_pieza == 'buena':
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET disponibles = disponibles + %s,
                        rentadas = rentadas - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad_recibida, cantidad_recibida, id_sucursal, id_pieza))
            elif estado_pieza == 'dañada':
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET daniadas = daniadas + %s,
                        rentadas = rentadas - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad_recibida, cantidad_recibida, id_sucursal, id_pieza))
            elif estado_pieza == 'faltante':
                # Faltante: no se devuelve nada, se descuenta todo lo que se esperaba
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET rentadas = rentadas - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad_esperada, id_sucursal, id_pieza))

        cursor.execute("""
            UPDATE rentas SET estado_renta = 'finalizada', fecha_entrada = %s WHERE id = %s
        """, (fecha_entrada_real or datetime.now().date(), renta_id))

        conn.commit()
        return jsonify({'success': True, 'folio': folio, 'nota_entrada_id': nota_entrada_id, 'pdf_url': pdf_url})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()


# === GENERAR PDF DE NOTA DE ENTRADA ===
@notas_entrada_bp.route('/pdf/<int:nota_entrada_id>')
def generar_pdf_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
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

        # === GENERAR PDF ===
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter

        # Fuente
        try:
            fuente_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
            pdfmetrics.registerFont(TTFont('Carlito', fuente_path))
            can.setFont("Carlito", 11)
        except:
            can.setFont("Helvetica", 11)

        # Título
        can.setFont("Helvetica-Bold", 16)
        can.drawString(200, 760, "NOTA DE ENTRADA")

        # Datos generales
        can.setFont("Helvetica", 11)
        y = 730
        can.drawString(40, y, f"Folio: {str(nota['folio']).zfill(5)}")
        can.drawString(400, y, f"Fecha: {nota['fecha'].strftime('%d/%m/%Y %H:%M')}")
        y -= 20
        can.drawString(40, y, f"Cliente: {nota['cliente_nombre']}")
        y -= 20
        can.drawString(40, y, f"Teléfono: {nota['celular']}")
        y -= 20
        can.drawString(40, y, f"Dirección de obra: {nota['direccion_obra']}")
        y -= 20
        can.drawString(40, y, f"Fecha límite de entrega: {nota['fecha_entrada_real'].strftime('%d/%m/%Y') if nota['fecha_entrada_real'] else 'Indefinida'}")
        y -= 30

        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 11)
        can.drawString(40, y, "Pieza")
        can.drawString(200, y, "Esperada")
        can.drawString(270, y, "Recibida")
        can.drawString(340, y, "Estado")
        can.drawString(420, y, "Costo Daño")
        can.drawString(510, y, "Obs")
        y -= 5
        can.line(40, y, 570, y)
        y -= 15

        # Datos de tabla
        can.setFont("Helvetica", 10)
        for p in piezas:
            if y < 100:  # Salto de página si se acaba el espacio
                can.showPage()
                y = 750
            can.drawString(40, y, p['nombre_pieza'][:25])
            can.drawString(200, y, str(p['cantidad_esperada']))
            can.drawString(270, y, str(p['cantidad_recibida']))
            can.drawString(340, y, p['estado_pieza'])
            can.drawString(420, y, f"${p['costo_daño']:.2f}")
            can.drawString(510, y, p['obs_pieza'][:20])
            y -= 18

        # Observaciones y cobro adicional
        y -= 10
        can.setFont("Helvetica-Bold", 11)
        can.drawString(40, y, "Observaciones:")
        y -= 15
        can.setFont("Helvetica", 10)
        can.drawString(40, y, nota['observaciones'][:100] if nota['observaciones'] else "-")
        y -= 25
        can.setFont("Helvetica-Bold", 11)
        can.drawString(40, y, f"Cobro adicional: ${nota['cobro_adicional']:.2f} - {nota['motivo_cobro']}")

        can.setFont("Helvetica", 8)
        can.drawString(40, 40, "Este documento fue generado automáticamente por el sistema.")

        can.save()
        packet.seek(0)

        return send_file(packet, download_name=f"nota_entrada_{str(nota['folio']).zfill(5)}.pdf", mimetype='application/pdf')

    except Exception as e:
        if cursor: cursor.close()
        if conn: conn.close()
        return f"Error al generar PDF: {str(e)}", 500
    
@notas_entrada_bp.route('/detalle/<int:nota_entrada_id>')
def ver_detalle_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM notas_entrada WHERE id = %s", (nota_entrada_id,))
    nota_entrada = cursor.fetchone()

    cursor.close()
    conn.close()

    if not nota_entrada: 
        return "Nota no encontrada", 404

    return render_template('detalle_nota.html', nota_entrada=nota_entrada)

@notas_entrada_bp.route('/crear_costo_extra/<int:renta_id>', methods=['POST'])
def crear_nota_costo_extra(renta_id):
    data = request.get_json()
    monto = float(data.get('monto', 0))
    motivo = data.get('motivo', '')
    usuario_id = 1  # De sesión, si aplica

    if monto <= 0:
        return jsonify({'success': False, 'error': 'Monto inválido'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio FROM notas_costo_extra")
        folio = str(cursor.fetchone()['siguiente_folio']).zfill(5)

        cursor.execute("""
            INSERT INTO notas_costo_extra (renta_id, folio, monto, motivo, usuario_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (renta_id, folio, monto, motivo, usuario_id))

        nota_extra_id = cursor.lastrowid
        pdf_url = f"/notas_entrada/pdf_costo_extra/{nota_extra_id}"

        cursor.execute("UPDATE notas_costo_extra SET pdf_url = %s WHERE id = %s", (pdf_url, nota_extra_id))
        conn.commit()

        return jsonify({'success': True, 'id': nota_extra_id, 'folio': folio, 'pdf_url': pdf_url})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()

@notas_entrada_bp.route('/pdf_renta/<int:renta_id>')
def generar_pdf_nota_entrada_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s ORDER BY id DESC LIMIT 1", (renta_id,))
    nota = cursor.fetchone()
    if not nota:
        return f"No hay nota de entrada para la renta {renta_id}", 404
    return redirect(url_for('notas_entrada.generar_pdf_nota_entrada', nota_entrada_id=nota['id']))


@notas_entrada_bp.route('/pdf_costo_extra/<int:nota_extra_id>')
def generar_pdf_costo_extra(nota_extra_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT nce.folio, nce.fecha, nce.monto, nce.motivo, 
                   c.nombre, c.apellido1, c.apellido2, c.telefono
            FROM notas_costo_extra nce
            JOIN rentas r ON nce.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE nce.id = %s
        """, (nota_extra_id,))
        nota = cursor.fetchone()

        if not nota:
            return "Nota de costo extra no encontrada", 404

        # === GENERAR PDF con diseño unificado ===
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter

        # Fuente personalizada si existe
        try:
            fuente_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
            pdfmetrics.registerFont(TTFont('Carlito', fuente_path))
            can.setFont("Carlito", 11)
        except:
            can.setFont("Helvetica", 11)

        # Título
        can.setFont("Helvetica-Bold", 16)
        can.drawString(180, 760, "NOTA DE COSTO EXTRA")

        # Datos generales
        can.setFont("Helvetica", 11)
        y = 730
        can.drawString(40, y, f"Folio: {str(nota['folio']).zfill(5)}")
        can.drawString(400, y, f"Fecha: {nota['fecha'].strftime('%d/%m/%Y %H:%M')}")
        y -= 20
        can.drawString(40, y, f"Cliente: {nota['nombre']} {nota['apellido1']} {nota['apellido2']}")
        y -= 20
        can.drawString(40, y, f"Teléfono: {nota['telefono']}")
        y -= 30

        # Detalles del costo extra
        can.setFont("Helvetica-Bold", 11)
        can.drawString(40, y, "Motivo del cobro:")
        y -= 18
        can.setFont("Helvetica", 11)
        can.drawString(40, y, nota['motivo'] or "-")
        y -= 30

        can.setFont("Helvetica-Bold", 11)
        can.drawString(40, y, f"Monto total a pagar: ${nota['monto']:.2f}")
        y -= 40

        # Pie de página
        can.setFont("Helvetica", 8)
        can.drawString(40, 40, "Este documento fue generado automáticamente por el sistema.")

        can.save()
        packet.seek(0)

        return send_file(
            packet,
            download_name=f"nota_costo_extra_{str(nota['folio']).zfill(5)}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        return f"Error al generar PDF de costo extra: {str(e)}", 500
    finally:
        cursor.close()
        conn.close()

@notas_entrada_bp.route('/pdf_costo_extra_renta/<int:renta_id>')
def generar_pdf_nota_costo_extra_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM notas_costo_extra 
        WHERE renta_id = %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (renta_id,))
    
    nota = cursor.fetchone()
    cursor.close()
    conn.close()

    if not nota:
        return f"No hay nota de costo extra para la renta {renta_id}", 404

    # 🔥 CORREGIDO AQUÍ
    return redirect(url_for('notas_entrada.generar_pdf_costo_extra', nota_extra_id=nota['id']))