document.addEventListener('DOMContentLoaded', function () {
    // Mostrar/ocultar fecha programada
    const chkProgramada = document.getElementById('renta_programada');
    const grupoProgramada = document.getElementById('fecha_programada_group');
    if (chkProgramada && grupoProgramada) {
        chkProgramada.addEventListener('change', function () {
            grupoProgramada.style.display = this.checked ? '' : 'none';
        });
    }

    // Mostrar/ocultar costo traslado
    const traslado = document.getElementById('traslado');
    const grupoTraslado = document.getElementById('costo_traslado_group');
    if (traslado && grupoTraslado) {
        traslado.addEventListener('change', function () {
            grupoTraslado.style.display = (this.value !== 'ninguno') ? '' : 'none';
        });
    }

    // Calcular días de renta
    function calcularDiasRenta() {
        const fechaInicio = document.getElementById('fecha_salida').value;
        const fechaFin = document.getElementById('fecha_entrada').value;
        if (!fechaFin) return null; // Sin fecha fin, días indefinidos
        let dias = 1;
        if (fechaInicio && fechaFin) {
            const inicio = new Date(fechaInicio);
            const fin = new Date(fechaFin);
            dias = Math.floor((fin - inicio) / (1000 * 60 * 60 * 24)) + 1;
            if (dias < 1) dias = 1;
        }
        return dias;
    }

    // Obtener precio correcto según días
    function obtenerPrecioProducto(productoId, dias) {
        const precios = window.preciosProductos ? window.preciosProductos[String(productoId)] : null;
        if (!precios) return 0;
        if (precios.precio_unico === 1) {
            return precios.precio_dia; // Siempre usa precio_dia, sin importar los días
        }
        if (dias === 1) return precios.precio_dia;
        if (dias >= 2 && dias <= 7) return precios.precio_7dias;
        if (dias >= 8 && dias <= 15) return precios.precio_15dias;
        if (dias >= 16 && dias <= 30) return precios.precio_30dias;
        if (dias >= 31) return precios.precio_31mas;
        return precios.precio_dia;
    }

    // Actualizar días y precios en la tabla de productos
    function actualizarDiasYPrecios() {
        const dias = calcularDiasRenta();
        document.querySelectorAll('#tabla-productos .dias').forEach(input => {
            if (dias === null) {
                input.value = '';
                input.placeholder = 'Indefinido';
            } else {
                input.value = dias;
                input.placeholder = '';
            }
        });
        document.querySelectorAll('#tabla-productos tr').forEach(fila => {
            const productoIdInput = fila.querySelector('input[name="producto_id[]"]');
            const costoInput = fila.querySelector('.costo');
            const cantidadInput = fila.querySelector('.cantidad');
            const subtotalInput = fila.querySelector('.subtotal');
            if (productoIdInput && costoInput && cantidadInput && subtotalInput) {
                const productoId = productoIdInput.value;
                let precio = 0;
                let subtotal = 0;
                if (dias !== null) {
                    precio = obtenerPrecioProducto(productoId, dias);
                    subtotal = (parseFloat(cantidadInput.value) * dias * precio);
                }
                costoInput.value = precio.toFixed(2);
                subtotalInput.value = subtotal.toFixed(2);
            }
        });
        calcularTotales();
    }

    // Listeners para fechas
    const fechaSalida = document.getElementById('fecha_salida');
    const fechaEntrada = document.getElementById('fecha_entrada');
    if (fechaSalida) fechaSalida.addEventListener('change', actualizarDiasYPrecios);
    if (fechaEntrada) fechaEntrada.addEventListener('change', actualizarDiasYPrecios);

    // Agregar productos a la tabla
    const btnAgregar = document.getElementById('agregar_producto');
    const selectProducto = document.getElementById('producto_select');
    const inputCantidad = document.getElementById('cantidad_producto');
    const tbody = document.querySelector('#tabla-productos tbody');

    if (btnAgregar && selectProducto && inputCantidad && tbody) {
        btnAgregar.addEventListener('click', function () {
            const productoId = selectProducto.value;
            const productoNombre = selectProducto.options[selectProducto.selectedIndex].text;
            const cantidad = parseInt(inputCantidad.value) || 1;
            const dias = calcularDiasRenta();
            const precio = obtenerPrecioProducto(productoId, dias);

            if (!productoId) return;

            const row = document.createElement('tr');
            row.innerHTML = `
        <td>
          <input type="hidden" name="producto_id[]" value="${productoId}">
          ${productoNombre}
        </td>
        <td><input type="number" name="cantidad[]" class="form-control cantidad" min="1" value="${cantidad}"></td>
        <td><input type="number" name="dias_renta[]" class="form-control dias" min="1" value="${dias}" readonly></td>
        <td><input type="number" name="costo_unitario[]" class="form-control costo" step="0.01" min="0" value="${precio.toFixed(2)}" readonly></td>
        <td><input type="number" class="form-control subtotal" step="0.01" min="0" value="${(cantidad * dias * precio).toFixed(2)}" readonly></td>
        <td><button type="button" class="btn btn-danger btn-sm btn-eliminar-producto"><i class="bi bi-trash"></i></button></td>
      `;
            tbody.appendChild(row);
            calcularTotales();
        });

        // Eliminar producto
        tbody.addEventListener('click', function (e) {
            if (e.target.closest('.btn-eliminar-producto')) {
                e.target.closest('tr').remove();
                calcularTotales();
            }
        });

        // Recalcular subtotales y totales al cambiar cantidad o costo (NO días)
        tbody.addEventListener('input', function (e) {
            if (e.target.classList.contains('cantidad') || e.target.classList.contains('costo')) {
                const fila = e.target.closest('tr');
                const cantidad = parseFloat(fila.querySelector('.cantidad').value) || 0;
                const dias = parseFloat(fila.querySelector('.dias').value) || 0;
                const costo = parseFloat(fila.querySelector('.costo').value) || 0;
                fila.querySelector('.subtotal').value = (cantidad * dias * costo).toFixed(2);
                calcularTotales();
            }
        });
    }

    function calcularTotales() {
        let subtotal = 0;
        document.querySelectorAll('#tabla-productos .subtotal').forEach(input => {
            subtotal += parseFloat(input.value) || 0;
        });
        // Obtén el traslado
        const traslado = parseFloat(document.getElementById('costo_traslado').value) || 0;
        const subtotalConTraslado = subtotal + traslado;
        const iva = subtotalConTraslado * 0.16;
        const total = subtotalConTraslado + iva;

        document.getElementById('subtotal_general').textContent = `$${subtotal.toFixed(2)}`;
        document.getElementById('traslado_general').textContent = `$${traslado.toFixed(2)}`;
        document.getElementById('iva_general').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('total_general').textContent = `$${total.toFixed(2)}`;
    }

    // Asegúrate de recalcular totales cuando cambie el traslado
    const trasladoInput = document.getElementById('costo_traslado');
    if (trasladoInput) {
        trasladoInput.addEventListener('input', calcularTotales);
    }

    const trasladoSelect = document.getElementById('traslado');
    const tipoTrasladoLabel = document.getElementById('tipo_traslado_label');
    function actualizarTipoTraslado() {
        let texto = '';
        if (trasladoSelect) {
            if (trasladoSelect.value === 'medio') texto = '(Medio)';
            else if (trasladoSelect.value === 'redondo') texto = '(Redondo)';
            else texto = '(Ninguno)';
        }
        if (tipoTrasladoLabel) tipoTrasladoLabel.textContent = texto;
    }
    if (trasladoSelect) trasladoSelect.addEventListener('change', actualizarTipoTraslado);
    // Llama una vez al cargar
    actualizarTipoTraslado();

})