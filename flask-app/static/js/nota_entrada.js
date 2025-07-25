document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-entrada');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNotaEntrada'));
            modal.show();

            // Limpiar campos
            document.getElementById('nota-entrada-folio').textContent = '-----';
            document.getElementById('nota-entrada-fecha').textContent = '--/--/---- --:--';
            document.getElementById('nota-entrada-cliente').textContent = '---';
            document.getElementById('nota-entrada-telefono').textContent = '---';
            document.getElementById('nota-entrada-direccion').textContent = '---';
            document.getElementById('nota-entrada-fecha-limite').textContent = '---';
            document.getElementById('nota-entrada-piezas').innerHTML = '<tr><td colspan="5" class="text-center text-muted">Cargando...</td></tr>';

            const btnGenerar = document.getElementById('btn-generar-nota-entrada');
            if (btnGenerar) {
                btnGenerar.disabled = true;
                btnGenerar.classList.add('disabled');
            }

            fetch(`/notas_entrada/preview/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('nota-entrada-piezas').innerHTML = `<tr><td colspan="5" class="text-danger">${data.error}</td></tr>`;
                        if (btnGenerar) {
                            btnGenerar.disabled = true;
                            btnGenerar.classList.add('disabled');
                        }

                        return;
                    }

                    // Llenar campos de info general
                    document.getElementById('nota-entrada-folio').textContent = data.folio;
                    document.getElementById('nota-entrada-fecha').textContent = data.fecha;
                    document.getElementById('nota-entrada-cliente').textContent = data.cliente;
                    document.getElementById('nota-entrada-telefono').textContent = data.telefono;
                    document.getElementById('nota-entrada-direccion').textContent = data.direccion_obra;
                    document.getElementById('nota-entrada-fecha-limite').textContent = data.fecha_limite;

                    // Mostrar botón de nota de costo extra si hay cobro adicional
                    if (data.cobro_retraso > 0) {
                        document.getElementById('btn-generar-costo-extra').style.display = 'inline-block';
                    } else {
                        document.getElementById('btn-generar-costo-extra').style.display = 'none';
                    }

                    // Mostrar alerta si hay retraso
                    const alertRetraso = document.getElementById('alerta-retraso');
                    const seccionCobroRetraso = document.getElementById('seccion-cobro-retraso');

                    if (data.hay_retraso) {
                        alertRetraso.style.display = 'block';
                        seccionCobroRetraso.style.display = 'flex'; // o 'block' según diseño
                        document.getElementById('cobro-retraso').value = data.cobro_retraso;
                        document.getElementById('motivo-cobro').value = `Retraso de ${data.dias_retraso} día(s)`;
                    } else {
                        alertRetraso.style.display = 'none';
                        seccionCobroRetraso.style.display = 'none';
                    }

                    // Llenar tabla de piezas
                    let piezasHtml = '';
                    if (data.piezas && data.piezas.length > 0) {
                        data.piezas.forEach(pieza => {
                            piezasHtml += `
                                <tr>
                                    <td>${pieza.nombre_pieza}</td>
                                    <td>${pieza.cantidad}</td>
                                    <td><input type="number" class="form-control form-control-sm cantidad-recibida" 
                                             value="${pieza.cantidad}" min="0" max="${pieza.cantidad}" 
                                             data-id-pieza="${pieza.id_pieza}"></td>
                                    <td>
                                        <select class="form-select form-select-sm estado-pieza" data-id-pieza="${pieza.id_pieza}">
                                            <option value="buena">Buena</option>
                                            <option value="dañada">Dañada</option>
                                            <option value="faltante">Faltante</option>
                                        </select>
                                    </td>
                                    <td><input type="number" class="form-control form-control-sm costo-daño" 
                                             value="0" min="0" step="0.01" 
                                             data-id-pieza="${pieza.id_pieza}" disabled></td>
                                </tr>
                            `;
                        });

                        // ✅ Habilitar botón porque hay piezas
                        if (btnGenerar) {
                            btnGenerar.disabled = false;
                            btnGenerar.classList.remove('disabled');
                        }
                    } else {
                        piezasHtml = '<tr><td colspan="5" class="text-center text-muted">Sin piezas para devolver</td></tr>';
                        if (btnGenerar) {
                            btnGenerar.disabled = true;
                            btnGenerar.classList.add('disabled');
                        }
                    }

                    document.getElementById('nota-entrada-piezas').innerHTML = piezasHtml;

                    // Evaluar si hay algún motivo para generar costo extra
                    let mostrarBotonCostoExtra = false;

                    // Verificar si ya hay cobro por retraso
                    if (parseFloat(data.cobro_retraso) > 0) {
                        mostrarBotonCostoExtra = true;
                    } else {
                        // Evaluar piezas con daño o faltantes
                        document.querySelectorAll('.estado-pieza').forEach(select => {
                            const estado = select.value;
                            const idPieza = select.dataset.idPieza;
                            const costo = parseFloat(document.querySelector(`.costo-daño[data-id-pieza="${idPieza}"]`).value) || 0;

                            if ((estado === 'dañada' || estado === 'faltante') && costo > 0) {
                                mostrarBotonCostoExtra = true;
                            }
                        });
                    }

                    document.getElementById('btn-generar-costo-extra').style.display = mostrarBotonCostoExtra ? 'inline-block' : 'none';


                    // Guardar datos globales
                    window.datosNotaEntrada = {
                        rentaId: rentaId,
                        piezas: data.piezas,
                        fecha_entrada_original: data.fecha_entrada_original
                    };
                })
                .catch(err => {
                    document.getElementById('nota-entrada-piezas').innerHTML = '<tr><td colspan="5" class="text-danger">Error al cargar datos.</td></tr>';
                    if (btnGenerar) {
                        btnGenerar.disabled = true;
                        btnGenerar.classList.add('disabled');
                    }
                    console.error('Error:', err);
                });
        }
    });

    // Manejar cambio de estado de pieza
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('estado-pieza') || e.target.classList.contains('costo-daño') || e.target.id === 'cobro-retraso') {
            const idPieza = e.target.dataset.idPieza;

            // Habilitar/deshabilitar input de daño según el estado
            if (e.target.classList.contains('estado-pieza')) {
                const costoDañoInput = document.querySelector(`.costo-daño[data-id-pieza="${idPieza}"]`);
                if (e.target.value === 'dañada') {
                    costoDañoInput.disabled = false;
                    costoDañoInput.focus();
                } else {
                    costoDañoInput.disabled = true;
                    costoDañoInput.value = '0';
                }
            }

            // Mostrar u ocultar botón de costo extra
            let mostrar = false;

            if (parseFloat(document.getElementById('cobro-retraso').value) > 0) {
                mostrar = true;
            } else {
                document.querySelectorAll('.estado-pieza').forEach(select => {
                    const estado = select.value;
                    const id = select.dataset.idPieza;
                    const costo = parseFloat(document.querySelector(`.costo-daño[data-id-pieza="${id}"]`).value) || 0;

                    if ((estado === 'dañada' || estado === 'faltante') && costo > 0) {
                        mostrar = true;
                    }
                });
            }

            document.getElementById('btn-generar-costo-extra').style.display = mostrar ? 'inline-block' : 'none';

            // 🧮 Calcular total actualizado
            calcularTotalCobro();
        }
    });
    // Enviar nota de entrada
    const form = document.getElementById('form-nota-entrada');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            const btn = document.getElementById('btn-generar-nota-entrada');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...';

            const rentaId = window.datosNotaEntrada.rentaId;

            // Recopilar datos de piezas
            const piezas = [];
            document.querySelectorAll('.cantidad-recibida').forEach(input => {
                const idPieza = input.dataset.idPieza;
                const cantidadEsperada = window.datosNotaEntrada.piezas.find(p => p.id_pieza == idPieza).cantidad;
                const cantidadRecibida = parseInt(input.value);
                const estadoPieza = document.querySelector(`.estado-pieza[data-id-pieza="${idPieza}"]`).value;
                const costoDaño = parseFloat(document.querySelector(`.costo-daño[data-id-pieza="${idPieza}"]`).value) || 0;

                piezas.push({
                    id_pieza: parseInt(idPieza),
                    cantidad_esperada: cantidadEsperada,
                    cantidad_recibida: cantidadRecibida,
                    estado_pieza: estadoPieza,
                    costo_daño: costoDaño,
                    observaciones: ''
                });
            });

            const payload = {
                fecha_entrada_real: document.getElementById('fecha-entrada-real').value || null,
                observaciones: document.getElementById('nota-entrada-observaciones').value,
                cobro_adicional: parseFloat(document.getElementById('cobro-retraso').value) || 0,
                motivo_cobro: document.getElementById('motivo-cobro').value,
                piezas: piezas
            };

            try {
                const res = await fetch(`/notas_entrada/crear/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();

                if (json.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalNotaEntrada'));
                    modal.hide();

                    Swal.fire({
                        title: 'Nota de entrada generada',
                        text: `Folio: ${json.folio}. ¿Deseas imprimir la nota de entrada ahora?`,
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, imprimir',
                        cancelButtonText: 'No'
                    }).then(result => {
                        if (result.isConfirmed) {
                            window.open(`/notas_entrada/pdf/${json.nota_entrada_id}`, '_blank');
                        }
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', json.error || 'No se pudo guardar la nota de entrada', 'error');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-left-circle"></i> Generar Nota de Entrada';
                }
            } catch (err) {
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-left-circle"></i> Generar Nota de Entrada';
            }
        });
    }
});