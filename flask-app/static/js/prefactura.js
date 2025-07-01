document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const target = e.target.closest('.btn-prefactura');
        if (target) {
            e.preventDefault();
            const rentaId = target.dataset.rentaId;

            // Cierra otros modales
            document.querySelectorAll('.modal.show').forEach(m => {
                bootstrap.Modal.getInstance(m)?.hide();
            });

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPrefacturaPago'));
            modal.show();

            // Reset campos
            const form = document.getElementById('form-pago-prefactura-pago');
            form.reset();
            form.dataset.rentaId = rentaId;

            document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-center text-muted">Cargando...</div>';
            document.getElementById('prefactura-total-pago').textContent = '0.00';
            document.getElementById('pago-total-pago').textContent = '0.00';

            fetch(`/rentas/prefactura/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
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

                    // Valores iniciales de pago
                    document.getElementById('metodo-pago-pago').value = 'efectivo';
                    document.getElementById('monto-recibido-pago').value = '';
                    document.getElementById('cambio-pago').textContent = '0.00';
                    document.getElementById('numero-seguimiento-pago').value = '';
                    document.getElementById('pago-efectivo-pago').style.display = '';
                    document.getElementById('pago-seguimiento-pago').style.display = 'none';
                })
                .catch(err => {
                    document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-danger">Error al cargar la prefactura.</div>';
                    console.error('Error al obtener prefactura:', err);
                });
        }
    });

    // Mostrar campos según método de pago
    const metodoPago = document.getElementById('metodo-pago-pago');
    if (metodoPago) {
        metodoPago.addEventListener('change', function () {
            const efectivo = document.getElementById('pago-efectivo-pago');
            const seguimiento = document.getElementById('pago-seguimiento-pago');
            efectivo.style.display = this.value === 'efectivo' ? '' : 'none';
            seguimiento.style.display = this.value !== 'efectivo' ? '' : 'none';
        });
    }

    // Calcular cambio
    const montoRecibido = document.getElementById('monto-recibido-pago');
    if (montoRecibido) {
        montoRecibido.addEventListener('input', function () {
            const total = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
            const recibido = parseFloat(this.value) || 0;
            const cambio = recibido - total;
            document.getElementById('cambio-pago').textContent = cambio > 0 ? cambio.toFixed(2) : '0.00';
        });
    }

    // Enviar prefactura/pago
    const form = document.getElementById('form-pago-prefactura-pago');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            const rentaId = form.dataset.rentaId;
            const tipo = document.getElementById('tipo_prefactura_pago').value;
            const metodo = document.getElementById('metodo-pago-pago').value;
            const monto = parseFloat(document.getElementById('pago-total-pago').textContent);
            const montoRecibido = metodo === 'efectivo' ? parseFloat(document.getElementById('monto-recibido-pago').value) : null;
            const cambio = metodo === 'efectivo' ? parseFloat(document.getElementById('cambio-pago').textContent) : null;
            const seguimiento = metodo !== 'efectivo' ? document.getElementById('numero-seguimiento-pago').value : null;

            const datos = {
                tipo: tipo,
                metodo_pago: metodo,
                monto: monto,
                monto_recibido: montoRecibido,
                cambio: cambio,
                numero_seguimiento: seguimiento
            };

            try {
                const res = await fetch(`/prefactura/guardar/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(datos)
                });

                const json = await res.json();
                if (json.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalPrefacturaPago'));
                    modal.hide();

                    Swal.fire({
                        title: 'Prefactura generada',
                        text: '¿Deseas imprimir la prefactura ahora?',
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, imprimir',
                        cancelButtonText: 'No'
                    }).then(result => {
                        if (result.isConfirmed) {
                            window.open(`/prefactura/pdf/${json.prefactura_id}`, '_blank');
                        }
                    });
                } else {
                    Swal.fire('Error', 'No se pudo registrar la prefactura', 'error');
                }
            } catch (err) {
                console.error('Error en el guardado:', err);
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
            }
        });
    }
});