document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal de detalle
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-ver-detalle');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleRenta'));
            modal.show();

            // Limpiar datos previos
            document.getElementById('detalle-renta-id').textContent = rentaId;
            document.getElementById('detalle-productos-tabla').innerHTML = 
                '<tr><td colspan="5" class="text-center text-muted">Cargando...</td></tr>';

            // Cargar datos
            fetch(`/rentas/detalle/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }
                    
                    cargarDatosRenta(data.renta);
                    cargarDatosCliente(data.cliente);
                    cargarProductos(data.productos);
                })
                .catch(err => {
                    console.error('Error:', err);
                    alert('Error al cargar los datos');
                });
        }
    });

    function cargarDatosRenta(renta) {
        // Estados con colores
        const estadoRentaClass = {
            'activo': 'bg-success',
            'programada': 'bg-warning',
            'finalizada': 'bg-secondary',
            'cancelada': 'bg-danger'
        };
        
        const estadoPagoClass = {
            'Pago realizado': 'bg-success',
            'Pago pendiente': 'bg-danger',
            'Parcialmente pagado': 'bg-warning'
        };

        document.getElementById('detalle-estado-renta').textContent = renta.estado_renta;
        document.getElementById('detalle-estado-renta').className = 
            `badge ${estadoRentaClass[renta.estado_renta.toLowerCase()] || 'bg-secondary'}`;
        
        document.getElementById('detalle-estado-pago').textContent = renta.estado_pago;
        document.getElementById('detalle-estado-pago').className = 
            `badge ${estadoPagoClass[renta.estado_pago] || 'bg-secondary'}`;
        
        document.getElementById('detalle-metodo-pago').textContent = renta.metodo_pago;
        document.getElementById('detalle-fecha-registro').textContent = renta.fecha_registro;
        document.getElementById('detalle-direccion-obra').textContent = renta.direccion_obra;
        document.getElementById('detalle-periodo-renta').textContent = 
            `${renta.fecha_salida} al ${renta.fecha_entrada}`;
        document.getElementById('detalle-fecha-limite').textContent = renta.fecha_limite;
        document.getElementById('detalle-traslado').textContent = renta.traslado;
        
        // Totales
        const subtotal = renta.total - renta.iva - renta.costo_traslado;
        document.getElementById('detalle-subtotal').textContent = `$${subtotal.toFixed(2)}`;
        document.getElementById('detalle-costo-traslado').textContent = `$${renta.costo_traslado.toFixed(2)}`;
        document.getElementById('detalle-iva').textContent = `$${renta.iva.toFixed(2)}`;
        document.getElementById('detalle-total').textContent = `$${renta.total.toFixed(2)}`;
        
        // Observaciones
        if (renta.observaciones) {
            document.getElementById('detalle-observaciones').textContent = renta.observaciones;
            document.getElementById('detalle-observaciones-section').style.display = 'block';
        } else {
            document.getElementById('detalle-observaciones-section').style.display = 'none';
        }
    }

    function cargarDatosCliente(cliente) {
        document.getElementById('detalle-codigo-cliente').textContent = cliente.codigo;
        document.getElementById('detalle-nombre-cliente').textContent = cliente.nombre;
        document.getElementById('detalle-telefono-cliente').textContent = cliente.telefono;
        document.getElementById('detalle-email-cliente').textContent = cliente.email;
        document.getElementById('detalle-rfc-cliente').textContent = cliente.rfc;
        document.getElementById('detalle-direccion-cliente').textContent = cliente.direccion;
    }

    function cargarProductos(productos) {
        const tbody = document.getElementById('detalle-productos-tabla');
        
        if (productos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay productos</td></tr>';
            return;
        }
        
        let html = '';
        productos.forEach(producto => {
            html += `
                <tr>
                    <td>${producto.nombre}</td>
                    <td>${producto.cantidad}</td>
                    <td>${producto.dias_renta || 'N/A'}</td>
                    <td>$${parseFloat(producto.costo_unitario || 0).toFixed(2)}</td>
                    <td>$${parseFloat(producto.subtotal || 0).toFixed(2)}</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    }

});