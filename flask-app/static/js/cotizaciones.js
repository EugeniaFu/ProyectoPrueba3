document.addEventListener('DOMContentLoaded', function() {
    let productosAgregados = [];
    let trasladoAgregado = null;
    let productoCounter = 0;

    // Elementos del DOM
    const diasRentaInput = document.getElementById('dias_renta');
    const requiereTrasladoCheck = document.getElementById('requiere_traslado');
    const tipoTrasladoContainer = document.getElementById('tipo_traslado_container');
    const costoTrasladoContainer = document.getElementById('costo_traslado_container');
    const tipoTrasladoSelect = document.getElementById('tipo_traslado');
    const costoTrasladoInput = document.getElementById('costo_traslado');
    const agregarTrasladoBtn = document.getElementById('agregar_traslado');
    const productoSelect = document.getElementById('producto_select');
    const cantidadInput = document.getElementById('cantidad_input');
    const precioUnitarioInput = document.getElementById('precio_unitario');
    const subtotalProductoInput = document.getElementById('subtotal_producto');
    const agregarProductoBtn = document.getElementById('agregar_producto');
    const productosTableBody = document.getElementById('productos_tbody');
    const mensajeSinProductos = document.getElementById('mensaje_sin_productos');
    const btnCrearCotizacion = document.getElementById('btn_crear_cotizacion');
    const productosHiddenInputs = document.getElementById('productos_hidden_inputs');

    // Establecer valor inicial de días
    diasRentaInput.value = 1;

    // Mostrar/ocultar campos de traslado
    requiereTrasladoCheck.addEventListener('change', function() {
        if (this.checked) {
            tipoTrasladoContainer.style.display = 'block';
            costoTrasladoContainer.style.display = 'block';
        } else {
            tipoTrasladoContainer.style.display = 'none';
            costoTrasladoContainer.style.display = 'none';
            costoTrasladoInput.value = '';
            // Eliminar traslado si existe
            if (trasladoAgregado) {
                eliminarTraslado();
            }
        }
        validarFormularioTraslado();
    });

    // Validar formulario de traslado
    function validarFormularioTraslado() {
        const valido = requiereTrasladoCheck.checked && 
                      tipoTrasladoSelect.value && 
                      costoTrasladoInput.value && 
                      parseFloat(costoTrasladoInput.value) > 0 &&
                      !trasladoAgregado;
        
        agregarTrasladoBtn.disabled = !valido;
    }

    // Listeners para validar traslado
    tipoTrasladoSelect.addEventListener('change', validarFormularioTraslado);
    costoTrasladoInput.addEventListener('input', validarFormularioTraslado);

    // Agregar traslado a la tabla
    agregarTrasladoBtn.addEventListener('click', function() {
        const tipoTraslado = tipoTrasladoSelect.value;
        const costoTraslado = parseFloat(costoTrasladoInput.value);
        
        const conceptoTraslado = `TRASLADO ${tipoTraslado.toUpperCase()}`;
        
        // Crear objeto de traslado
        trasladoAgregado = {
            tipo: 'traslado',
            concepto: conceptoTraslado,
            tipo_traslado: tipoTraslado,
            costo: costoTraslado
        };
        
        // Agregar fila a la tabla (solo concepto y precio para traslado)
        const fila = document.createElement('tr');
        fila.setAttribute('data-tipo', 'traslado');
        fila.innerHTML = `
            <td><strong>${conceptoTraslado}</strong></td>
            <td colspan="3" class="text-center text-muted">-</td>
            <td>$${costoTraslado.toFixed(2)}</td>
            <td>
                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarTraslado()">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        `;
        productosTableBody.appendChild(fila);
        
        // Deshabilitar el botón
        agregarTrasladoBtn.disabled = true;
        
        // Ocultar mensaje sin productos
        mensajeSinProductos.style.display = 'none';
        
        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    });

    // Eliminar traslado
    window.eliminarTraslado = function() {
        // Remover de la tabla
        const fila = document.querySelector('tr[data-tipo="traslado"]');
        if (fila) {
            fila.remove();
        }
        
        // Limpiar objeto
        trasladoAgregado = null;
        
        // Mostrar mensaje si no hay productos
        if (productosAgregados.length === 0) {
            mensajeSinProductos.style.display = 'block';
        }
        
        // Habilitar botón de agregar traslado
        validarFormularioTraslado();
        
        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    };

    // Cuando cambie el producto seleccionado
    productoSelect.addEventListener('change', function() {
        const productoId = this.value;
        const diasRenta = parseInt(diasRentaInput.value) || 1;
        
        if (productoId && diasRenta) {
            // Obtener precio automáticamente
            fetch(`/cotizaciones/precios/${productoId}/${diasRenta}`)
                .then(response => response.json())
                .then(data => {
                    if (data.precio) {
                        precioUnitarioInput.value = data.precio.toFixed(2);
                        calcularSubtotalProducto();
                    }
                })
                .catch(error => console.error('Error:', error));
        } else {
            precioUnitarioInput.value = '';
            subtotalProductoInput.value = '';
        }
        validarFormularioProducto();
    });

    // Cuando cambien los días de renta
    diasRentaInput.addEventListener('change', function() {
        const diasRenta = parseInt(this.value) || 1;
        
        // Actualizar precios de productos existentes
        productosAgregados.forEach(producto => {
            if (producto.tipo === 'producto') {
                fetch(`/cotizaciones/precios/${producto.producto_id}/${diasRenta}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.precio) {
                            producto.precio_unitario = data.precio;
                            producto.dias = diasRenta;
                            // Recalcular subtotal con la nueva fórmula
                            producto.subtotal = producto.cantidad * producto.precio_unitario * diasRenta;
                            
                            // Actualizar en la tabla
                            const fila = document.querySelector(`tr[data-producto-id="${producto.producto_id}"]`);
                            if (fila) {
                                fila.querySelector('.dias').textContent = diasRenta;
                                fila.querySelector('.precio-unitario').textContent = `$${producto.precio_unitario.toFixed(2)}`;
                                fila.querySelector('.subtotal').textContent = `$${producto.subtotal.toFixed(2)}`;
                            }
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
        });
        
        // Recalcular precio del producto seleccionado
        if (productoSelect.value) {
            productoSelect.dispatchEvent(new Event('change'));
        }
        
        // Recalcular totales después de un pequeño delay
        setTimeout(() => {
            calcularTotales();
            actualizarHiddenInputs();
        }, 100);
    });

    // Cuando cambien los días de renta, también recalcular el subtotal del producto en selección
    diasRentaInput.addEventListener('input', function() {
        calcularSubtotalProducto();
    });

    // Cuando cambie la cantidad
    cantidadInput.addEventListener('input', function() {
        calcularSubtotalProducto();
        validarFormularioProducto();
    });

    // Calcular subtotal del producto (PRECIO × CANTIDAD × DÍAS)
    function calcularSubtotalProducto() {
        const cantidad = parseFloat(cantidadInput.value) || 0;
        const precio = parseFloat(precioUnitarioInput.value) || 0;
        const dias = parseInt(diasRentaInput.value) || 1;
        const subtotal = cantidad * precio * dias;
        subtotalProductoInput.value = subtotal.toFixed(2);
    }

    // Validar formulario de producto
    function validarFormularioProducto() {
        const valido = productoSelect.value && 
                      cantidadInput.value && 
                      parseFloat(cantidadInput.value) > 0 && 
                      precioUnitarioInput.value;
        
        agregarProductoBtn.disabled = !valido;
    }

    // Agregar producto a la tabla
    agregarProductoBtn.addEventListener('click', function() {
        const productoId = productoSelect.value;
        const productoNombre = productoSelect.options[productoSelect.selectedIndex].text;
        const cantidad = parseFloat(cantidadInput.value);
        const precioUnitario = parseFloat(precioUnitarioInput.value);
        const diasRenta = parseInt(diasRentaInput.value) || 1;
        const subtotal = cantidad * precioUnitario * diasRenta; // Incluir días en el cálculo

        // Verificar si el producto ya existe
        const productoExistente = productosAgregados.find(p => p.producto_id === productoId);
        
        if (productoExistente) {
            // Actualizar cantidad y subtotal
            productoExistente.cantidad += cantidad;
            productoExistente.subtotal = productoExistente.cantidad * productoExistente.precio_unitario * diasRenta;
            
            // Actualizar en la tabla
            const fila = document.querySelector(`tr[data-producto-id="${productoId}"]`);
            fila.querySelector('.cantidad').textContent = productoExistente.cantidad;
            fila.querySelector('.subtotal').textContent = `$${productoExistente.subtotal.toFixed(2)}`;
        } else {
            // Agregar nuevo producto
            const producto = {
                tipo: 'producto',
                producto_id: productoId,
                nombre: productoNombre,
                cantidad: cantidad,
                precio_unitario: precioUnitario,
                subtotal: subtotal,
                dias: diasRenta,
                index: productoCounter++
            };
            
            productosAgregados.push(producto);
            
            // Agregar fila a la tabla
            const fila = document.createElement('tr');
            fila.setAttribute('data-producto-id', productoId);
            fila.innerHTML = `
                <td>${productoNombre}</td>
                <td class="cantidad">${cantidad}</td>
                <td class="dias">${diasRenta}</td>
                <td class="precio-unitario">$${precioUnitario.toFixed(2)}</td>
                <td class="subtotal">$${subtotal.toFixed(2)}</td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" onclick="eliminarProducto('${productoId}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            productosTableBody.appendChild(fila);
        }

        // Limpiar formulario
        productoSelect.value = '';
        cantidadInput.value = '';
        precioUnitarioInput.value = '';
        subtotalProductoInput.value = '';
        agregarProductoBtn.disabled = true;

        // Ocultar mensaje sin productos
        mensajeSinProductos.style.display = 'none';
        
        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    });

    // Eliminar producto
    window.eliminarProducto = function(productoId) {
        // Remover del array
        productosAgregados = productosAgregados.filter(p => p.producto_id !== productoId);
        
        // Remover de la tabla
        const fila = document.querySelector(`tr[data-producto-id="${productoId}"]`);
        fila.remove();
        
        // Mostrar mensaje si no hay productos ni traslado
        if (productosAgregados.length === 0 && !trasladoAgregado) {
            mensajeSinProductos.style.display = 'block';
        }
        
        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    };

    // Calcular totales
    function calcularTotales() {
        let subtotalTotal = 0;
        
        // Sumar productos
        productosAgregados.forEach(producto => {
            subtotalTotal += producto.subtotal;
        });
        
        // Sumar traslado
        if (trasladoAgregado) {
            subtotalTotal += trasladoAgregado.costo;
        }
        
        const iva = subtotalTotal * 0.16;
        const total = subtotalTotal + iva;

        // Actualizar displays
        document.getElementById('subtotal-display').textContent = `$${subtotalTotal.toFixed(2)}`;
        document.getElementById('iva-display').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('total-display').textContent = `$${total.toFixed(2)}`;
    }

    // Actualizar inputs ocultos
    function actualizarHiddenInputs() {
        productosHiddenInputs.innerHTML = '';
        
        // Agregar productos
        productosAgregados.forEach((producto, index) => {
            productosHiddenInputs.innerHTML += `
                <input type="hidden" name="productos[${index}][producto_id]" value="${producto.producto_id}">
                <input type="hidden" name="productos[${index}][cantidad]" value="${producto.cantidad}">
                <input type="hidden" name="productos[${index}][precio_unitario]" value="${producto.precio_unitario}">
            `;
        });
    }

    // Validar formulario completo
    function validarFormularioCompleto() {
        const valido = productosAgregados.length > 0 || trasladoAgregado;
        btnCrearCotizacion.disabled = !valido;
    }

    // Limpiar todo al cerrar el modal
    document.getElementById('modalNuevaCotizacion').addEventListener('hidden.bs.modal', function() {
        // Limpiar productos y traslado
        productosAgregados = [];
        trasladoAgregado = null;
        productosTableBody.innerHTML = '';
        mensajeSinProductos.style.display = 'block';
        
        // Limpiar formulario
        document.querySelector('#modalNuevaCotizacion form').reset();
        
        // Restaurar valor inicial de días
        diasRentaInput.value = 1;
        
        // Ocultar containers
        tipoTrasladoContainer.style.display = 'none';
        costoTrasladoContainer.style.display = 'none';
        
        // Resetear botones
        agregarProductoBtn.disabled = true;
        agregarTrasladoBtn.disabled = true;
        btnCrearCotizacion.disabled = true;
        
        // Limpiar inputs ocultos
        productosHiddenInputs.innerHTML = '';
        
        // Resetear totales
        document.getElementById('subtotal-display').textContent = '$0.00';
        document.getElementById('iva-display').textContent = '$0.00';
        document.getElementById('total-display').textContent = '$0.00';
    });
});