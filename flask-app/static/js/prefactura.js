document.addEventListener('DOMContentLoaded', function () {
    // Delegación de eventos para btn-prefactura
    document.body.addEventListener('click', function (e) {
        const target = e.target.closest('.btn-prefactura');
        if (target) {
            e.preventDefault();
            const rentaId = target.dataset.rentaId;
            const fechaEntrada = target.dataset.fechaEntrada;
            console.log('Botón prefactura clickeado', rentaId, fechaEntrada);

            // Cierra otros modales abiertos
            document.querySelectorAll('.modal.show').forEach(m => {
                bootstrap.Modal.getInstance(m)?.hide();
            });

            // Muestra el modal ANTES del fetch
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPrefacturaPago'));
            modal.show();

            // Limpia el contenido mientras carga
            document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-center text-muted">Cargando...</div>';
            document.getElementById('prefactura-total-pago').textContent = '0.00';
            document.getElementById('pago-total-pago').textContent = '0.00';

            fetch(`/rentas/prefactura/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    console.log('Datos recibidos:', data);
                    // Llenar tabla de desglose
                    let html = `
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>Producto</th>
                                    <th>Cantidad</th>
                                    <th>Días</th>
                                    <th>Costo unitario</th>
                                    <th>Subtotal</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    data.detalle.forEach(item => {
                        html += `
                            <tr>
                                <td>${item.nombre}</td>
                                <td>${item.cantidad}</td>
                                <td>${item.dias_renta}</td>
                                <td>$${parseFloat(item.costo_unitario).toFixed(2)}</td>
                                <td>$${parseFloat(item.subtotal).toFixed(2)}</td>
                            </tr>
                        `;
                    });
                    html += `</tbody></table>`;
                    document.getElementById('prefactura-detalle-pago').innerHTML = html;
                    document.getElementById('prefactura-total-pago').textContent = parseFloat(data.total_con_iva).toFixed(2);
                    document.getElementById('pago-total-pago').textContent = parseFloat(data.total_con_iva).toFixed(2);

                    // Guardar rentaId para el pago
                    const formPago = document.getElementById('form-pago-prefactura-pago');
                    if (formPago) {
                        formPago.dataset.rentaId = rentaId;
                    }

                    // Limpia campos de pago
                    document.getElementById('metodo-pago-pago').value = 'efectivo';
                    document.getElementById('monto-recibido-pago').value = '';
                    document.getElementById('cambio-pago').textContent = '0.00';
                    document.getElementById('numero-seguimiento-pago').value = '';
                    document.getElementById('pago-efectivo-pago').style.display = '';
                    document.getElementById('pago-seguimiento-pago').style.display = 'none';
                })
                .catch(err => {
                    document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-danger">Error al cargar la prefactura.</div>';
                    console.error('Error en fetch:', err);
                });
        }
    });

    // Mostrar campos según método de pago
    const metodoPago = document.getElementById('metodo-pago-pago');
    if (metodoPago) {
        metodoPago.addEventListener('change', function () {
            const pagoEfectivo = document.getElementById('pago-efectivo-pago');
            const pagoSeguimiento = document.getElementById('pago-seguimiento-pago');
            if (pagoEfectivo && pagoSeguimiento) {
                pagoEfectivo.style.display = this.value === 'efectivo' ? '' : 'none';
                pagoSeguimiento.style.display =
                    (this.value === 'tarjeta_debito' || this.value === 'tarjeta_credito' || this.value === 'transferencia') ? '' : 'none';
            }
        });
    }

    // Calcular cambio en efectivo
    const montoRecibido = document.getElementById('monto-recibido-pago');
    if (montoRecibido) {
        montoRecibido.addEventListener('input', function () {
            const total = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
            const recibido = parseFloat(this.value) || 0;
            document.getElementById('cambio-pago').textContent = (recibido - total > 0) ? (recibido - total).toFixed(2) : '0.00';
        });
    }

    // Procesar pago exitoso
    const formPagoPrefactura = document.getElementById('form-pago-prefactura-pago');
    if (formPagoPrefactura) {
        formPagoPrefactura.addEventListener('submit', function (e) {
            e.preventDefault();
            const rentaId = this.dataset.rentaId;
            const tipo = document.getElementById('tipo_prefactura_pago').value;
            const metodo = document.getElementById('metodo-pago-pago').value;
            const monto = parseFloat(document.getElementById('pago-total-pago').textContent);
            const montoRecibido = metodo === 'efectivo' ? parseFloat(document.getElementById('monto-recibido-pago').value) : null;
            const cambio = metodo === 'efectivo' ? parseFloat(document.getElementById('cambio-pago').textContent) : null;
            const numeroSeguimiento = metodo !== 'efectivo' ? document.getElementById('numero-seguimiento-pago').value : null;

            fetch(`/rentas/prefactura/pago/${rentaId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tipo: tipo,
                    metodo_pago: metodo,
                    monto: monto,
                    monto_recibido: montoRecibido,
                    cambio: cambio,
                    numero_seguimiento: numeroSeguimiento
                })
            })
                .then(resp => resp.json())
                .then(data => {
                    if (data.success) {
                        // Abrir el PDF generado en una nueva pestaña
                        window.open(`/static/notas/prefactura_${rentaId}.pdf`, '_blank');
                        window.location.reload();
                    } else {
                        alert('Error al registrar el pago');
                    }
                });
        });
    }

});