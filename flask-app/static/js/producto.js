let filtroActual = 'todos';

function mostrarSelectorPiezas() {
  var tipo = document.getElementById('tipoProducto').value;
  document.getElementById('piezasIndividual').style.display = tipo === 'individual' ? 'block' : 'none';
  document.getElementById('piezasKit').style.display = tipo === 'conjunto' ? 'block' : 'none';
}

function agregarKitPiezaRow() {
  var container = document.getElementById('kitPiezasContainer');
  var row = document.createElement('div');
  row.className = 'row mb-2 kit-pieza-row';
  row.innerHTML = `
    <div class="col-8">
      <select class="form-select" name="pieza_kit[]">
        ${window.piezasOptionsHTML || ''}
      </select>
    </div>
    <div class="col-3">
      <input type="number" class="form-control" name="cantidad_kit[]" min="1" value="1" required>
    </div>
    <div class="col-1">
      <button type="button" class="btn btn-danger btn-sm" onclick="eliminarKitPiezaRow(this)">&times;</button>
    </div>
  `;
  container.appendChild(row);
}

function eliminarKitPiezaRow(btn) {
  btn.closest('.kit-pieza-row').remove();
}

function aplicarFiltros() {
  const filtro = filtroActual;
  const texto = (document.getElementById('buscadorProductos')?.value || '').toLowerCase();

  document.querySelectorAll('.table-inventario tbody tr').forEach(function(row) {
    const estatus = row.getAttribute('data-estatus');
    const contenido = row.innerText.toLowerCase();

    // Aplica ambos filtros
    const coincideEstatus = (filtro === 'todos') || (estatus === filtro);
    const coincideTexto = contenido.includes(texto);

    row.style.display = (coincideEstatus && coincideTexto) ? '' : 'none';
  });
}

// Filtro de estatus
function filtrarProductos(estatus) {
  filtroActual = estatus;
  aplicarFiltros();
}
window.filtrarProductos = filtrarProductos;

document.addEventListener('DOMContentLoaded', function() {
  // Guardar las opciones de piezas para JS dinámico
  var select = document.querySelector('#piezasKit select.form-select');
  if (select) {
    window.piezasOptionsHTML = select.innerHTML;
  }

  // Buscador de productos
  var buscador = document.getElementById('buscadorProductos');
  if (buscador) {
    buscador.addEventListener('keyup', aplicarFiltros);
  }

  // Filtro de estatus: por defecto mostrar todos
  filtrarProductos('todos');
});

// Para agregar/quitar piezas en edición de kit
function agregarKitPiezaRowEditar(idProducto) {
  var container = document.getElementById('kitPiezasContainerEditar' + idProducto);
  var row = document.createElement('div');
  row.className = 'row mb-2 kit-pieza-row';
  row.innerHTML = `
    <div class="col-7">
      <select class="form-select" name="pieza_kit[]">
        ${window.piezasOptionsHTML || ''}
      </select>
    </div>
    <div class="col-3">
      <input type="number" class="form-control" name="cantidad_kit[]" min="1" value="1" required>
    </div>
    <div class="col-2">
      <button type="button" class="btn btn-danger btn-sm" onclick="eliminarKitPiezaRowEditar(this)">&times;</button>
    </div>
  `;
  container.appendChild(row);
}

function eliminarKitPiezaRowEditar(btn) {
  btn.closest('.kit-pieza-row').remove();
}

// Guarda las opciones de piezas para JS dinámico (ya lo tienes en tu código)
document.addEventListener('DOMContentLoaded', function() {
  var select = document.querySelector('#piezasKit select.form-select');
  if (select) {
    window.piezasOptionsHTML = select.innerHTML;
  }
});