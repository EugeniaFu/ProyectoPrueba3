document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-salida');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNotaSalida'));
            modal.show();

            // Limpia campos
            document.getElementById('nota-salida-folio').textContent = '-----';
            document.getElementById('nota-salida-fecha').textContent = '--/--/---- --:--';
            document.getElementById('nota-salida-cliente').textContent = '---';
            document.getElementById('nota-salida-celular').textContent = '---';
            document.getElementById('nota-salida-direccion').textContent = '---';
            document.getElementById('nota-salida-periodo').textContent = '--/--/---- a indefinido';
            document.getElementById('nota-salida-piezas').innerHTML = '<tr><td colspan="2" class="text-center text-muted">Cargando...</td></tr>';

            fetch(`/notas_salida/preview/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('nota-salida-piezas').innerHTML = `<tr><td colspan="2" class="text-danger">${data.error}</td></tr>`;
                        return;
                    }
                    document.getElementById('nota-salida-folio').textContent = data.folio;
                    document.getElementById('nota-salida-fecha').textContent = data.fecha;
                    document.getElementById('nota-salida-cliente').textContent = data.cliente;
                    document.getElementById('nota-salida-celular').textContent = data.celular;
                    document.getElementById('nota-salida-direccion').textContent = data.direccion_obra;
                    document.getElementById('nota-salida-periodo').textContent = data.periodo;

                    let piezasHtml = '';
                    if (data.piezas && data.piezas.length > 0) {
                        data.piezas.forEach(pieza => {
                            piezasHtml += `
                                <tr>
                                    <td>${pieza.nombre_pieza}</td>
                                    <td>${pieza.cantidad}</td>
                                </tr>
                            `;
                        });
                    } else {
                        piezasHtml = '<tr><td colspan="2" class="text-center text-muted">Sin piezas asociadas</td></tr>';
                    }
                    document.getElementById('nota-salida-piezas').innerHTML = piezasHtml;

                    window.piezasNotaSalida = data.piezas.map(p => ({
                        id_pieza: p.id_pieza, // Debe venir en el JSON del endpoint preview
                        cantidad: p.cantidad
                    }));

                })
                .catch(err => {
                    document.getElementById('nota-salida-piezas').innerHTML = '<tr><td colspan="2" class="text-danger">Error al cargar la nota de salida.</td></tr>';
                    console.error('Error al obtener nota de salida:', err);
                });
        }
    });

    // Enviar nota de salida
    const form = document.getElementById('form-nota-salida');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            // Obtén el rentaId del último modal abierto
            const rentaId = document.querySelector('.btn-nota-salida.active')?.dataset.rentaId ||
                document.querySelector('.btn-nota-salida[data-renta-id]')?.dataset.rentaId;

            // Si no tienes forma de saber el rentaId así, guárdalo en una variable global al abrir el modal

            // Obtén piezas del modal
            const piezas = [];
            document.querySelectorAll('#nota-salida-piezas tr').forEach(row => {
                const nombre = row.children[0]?.textContent;
                const cantidad = parseInt(row.children[1]?.textContent);
                // Si tienes el id_pieza en data-id, úsalo:
                // const id_pieza = row.dataset.idPieza;
                // piezas.push({ id_pieza, cantidad });
                // Si no, deberás modificar el renderizado para incluir el id_pieza como data-id
            });

            // Pero lo ideal es que al cargar el modal, guardes el array de piezas (con id_pieza y cantidad) en una variable global.
            // Aquí un ejemplo usando una variable global:
            // window.piezasNotaSalida = [{id_pieza: 1, cantidad: 5}, ...];

            // Recoge los datos del formulario
            const numero_referencia = document.getElementById('nota-salida-referencia').value;
            const observaciones = document.getElementById('nota-salida-observaciones').value;

            // Usa la variable global window.piezasNotaSalida si la llenaste al cargar el modal
            const payload = {
                numero_referencia,
                observaciones,
                piezas: window.piezasNotaSalida || []
            };

            try {
                const res = await fetch(`/notas_salida/crear/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                if (json.success) {
                    Swal.fire('¡Nota de salida generada!', `Folio: ${json.folio}`, 'success')
                        .then(() => window.location.reload());
                } else {
                    Swal.fire('Error', json.error || 'No se pudo guardar la nota de salida', 'error');
                }
            } catch (err) {
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
            }
        });
    }


});