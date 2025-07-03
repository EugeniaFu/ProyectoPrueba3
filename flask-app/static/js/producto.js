let filtroActual = 'todos';

// Para cambiar el tipo de producto en edición
function mostrarSelectorPiezasEditar(idProducto) {
  const tipo = document.getElementById('tipoProductoEditar' + idProducto).value;
  document.getElementById('piezasIndividualEditar' + idProducto).style.display = tipo === 'individual' ? 'block' : 'none';
  document.getElementById('piezasKitEditar' + idProducto).style.display = tipo === 'conjunto' ? 'block' : 'none';
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

  document.querySelectorAll('.table-inventario tbody tr').forEach(function (row) {
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

document.addEventListener('DOMContentLoaded', function () {
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
document.addEventListener('DOMContentLoaded', function () {
  var select = document.querySelector('#piezasKit select.form-select');
  if (select) {
    window.piezasOptionsHTML = select.innerHTML;
  }
});

// --------- CORRECCIÓN PARA CAMPOS DE PRECIOS NUEVO PRODUCTO ---------
function toggleCamposPrecioNuevo() {
  const check = document.getElementById('precioUnicoNuevo');
  // El campo de precio por día siempre está visible, solo cambia required
  document.querySelector('input[name="precio_dia"]').required = true;
  // Los campos de rango se ocultan si es precio único
  const camposRangos = document.getElementById('camposRangosNuevo');
  if (check.checked) {
    camposRangos.style.display = 'none';
    document.querySelectorAll('input[name="precio_7dias"], input[name="precio_15dias"], input[name="precio_30dias"], input[name="precio_31mas"]').forEach(function (input) {
      input.required = false;
    });
  } else {
    camposRangos.style.display = 'flex';
    document.querySelectorAll('input[name="precio_7dias"], input[name="precio_15dias"], input[name="precio_30dias"], input[name="precio_31mas"]').forEach(function (input) {
      input.required = true;
    });
  }
}


// Para editar producto
function toggleCamposPrecioEditar(idProducto) {
  const check = document.getElementById('precioUnicoEditar' + idProducto);
  // El campo de precio por día siempre está visible, solo cambia required
  const inputDia = document.querySelector(`#campoPrecioDiaEditar${idProducto} input[name="precio_dia"]`);
  if (inputDia) inputDia.required = true;
  // Los campos de rango se ocultan si es precio único
  const camposRangos = document.getElementById('camposRangosEditar' + idProducto);
  if (check.checked) {
    camposRangos.style.display = 'none';
    document.querySelectorAll(`#camposRangosEditar${idProducto} input[name="precio_7dias"], #camposRangosEditar${idProducto} input[name="precio_15dias"], #camposRangosEditar${idProducto} input[name="precio_30dias"], #camposRangosEditar${idProducto} input[name="precio_31mas"]`).forEach(function (input) {
      input.required = false;
    });
  } else {
    camposRangos.style.display = 'flex';
    document.querySelectorAll(`#camposRangosEditar${idProducto} input[name="precio_7dias"], #camposRangosEditar${idProducto} input[name="precio_15dias"], #camposRangosEditar${idProducto} input[name="precio_30dias"], #camposRangosEditar${idProducto} input[name="precio_31mas"]`).forEach(function (input) {
      input.required = true;
    });
  }
}

function mostrarSelectorPiezas() {
  const tipo = document.getElementById('tipoProducto').value;
  document.getElementById('piezasIndividual').style.display = tipo === 'individual' ? 'block' : 'none';
  document.getElementById('piezasKit').style.display = tipo === 'conjunto' ? 'block' : 'none';
}

document.addEventListener('DOMContentLoaded', function () {
  // ...existing code...

  // Cuando se abre el modal de nuevo producto, mostrar el selector correcto
  const modalNuevo = document.getElementById('modalNuevoProducto');
  if (modalNuevo) {
    modalNuevo.addEventListener('show.bs.modal', function () {
      mostrarSelectorPiezas();
    });
  }


  document.addEventListener('DOMContentLoaded', function () {
    const formNuevoProducto = document.getElementById('form-nuevo-producto');
    const btnGuardarProducto = document.getElementById('btn-guardar-producto');
    if (formNuevoProducto && btnGuardarProducto) {
      formNuevoProducto.addEventListener('submit', function () {
        btnGuardarProducto.disabled = true;
        btnGuardarProducto.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';
      });
    }
  });


});