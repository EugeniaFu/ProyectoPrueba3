// ========================================
// VARIABLES GLOBALES
// ========================================
let archivosSeleccionados = [];
let direccionCompleta = false;

// ========================================
// FUNCIONALIDAD DE DOCUMENTOS Y ARCHIVOS
// ========================================

document.getElementById('documentos').addEventListener('change', function (e) {
    for (let file of e.target.files) {
        archivosSeleccionados.push({ file, tipo: 'otro' });
    }
    e.target.value = '';
    renderPreview();
});

function renderPreview() {
    const preview = document.getElementById('previewDocs');
    preview.innerHTML = '';
    if (archivosSeleccionados.length === 0) {
        preview.innerHTML = '<small class="text-muted">No hay archivos seleccionados.</small>';
        return;
    }
    archivosSeleccionados.forEach((item, idx) => {
        let icon = '';
        if (item.file.type === 'application/pdf') {
            icon = '<i class="bi bi-file-earmark-pdf text-danger" style="font-size:2rem;"></i>';
        } else if (item.file.type.startsWith('image/')) {
            icon = '<i class="bi bi-file-earmark-image text-primary" style="font-size:2rem;"></i>';
        } else {
            icon = '<i class="bi bi-file-earmark" style="font-size:2rem;"></i>';
        }
        const size = (item.file.size / 1024 / 1024).toFixed(2) + ' MB';
        const url = URL.createObjectURL(item.file);
        preview.innerHTML += `
            <div class="d-flex align-items-center border rounded p-2 mb-2" style="background:#f8fafc;">
                ${icon}
                <div class="ms-3 flex-grow-1">
                    <div class="fw-bold">${item.file.name}</div>
                    <div class="text-muted" style="font-size:0.9em;">${size}</div>
                    <select class="form-select form-select-sm mt-1" style="width:auto;display:inline-block"
                        onchange="cambiarTipoDoc(${idx}, this.value)">
                        <option value="ine" ${item.tipo === 'ine' ? 'selected' : ''}>INE</option>
                        <option value="comprobante" ${item.tipo === 'comprobante' ? 'selected' : ''}>Comprobante</option>
                        <option value="licencia" ${item.tipo === 'licencia' ? 'selected' : ''}>Licencia</option>
                        <option value="otro" ${item.tipo === 'otro' ? 'selected' : ''}>Otro</option>
                    </select>
                </div>
                <a href="${url}" target="_blank" class="btn btn-outline-secondary btn-sm me-2" title="Vista previa">
                    <i class="bi bi-eye"></i>
                </a>
                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarArchivo(${idx})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
    });
}

function cambiarTipoDoc(idx, tipo) {
    archivosSeleccionados[idx].tipo = tipo;
}

function eliminarArchivo(idx) {
    archivosSeleccionados.splice(idx, 1);
    renderPreview();
}

// ========================================
// FUNCIONALIDAD DE CÁMARA
// ========================================

let video = document.getElementById('video');
let canvas = document.getElementById('canvas');
let btnCamara = document.getElementById('btnCamara');
let btnFoto = document.getElementById('btnFoto');
let previewFoto = document.getElementById('previewFoto');
let fotoInput = document.getElementById('foto_documento');
let stream = null;

btnCamara.onclick = async function () {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        video.style.display = 'block';
        btnFoto.style.display = 'inline-block';
    } catch (error) {
        alert('Error al acceder a la cámara: ' + error.message);
    }
};

btnFoto.onclick = function () {
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    let dataUrl = canvas.toDataURL('image/png');
    
    fetch(dataUrl)
        .then(res => res.blob())
        .then(blob => {
            let file = new File([blob], "foto_documento.png", { type: "image/png" });
            archivosSeleccionados.push({ file, tipo: 'ine' });
            renderPreview();
        });
    
    previewFoto.src = dataUrl;
    previewFoto.style.display = 'block';
    fotoInput.value = dataUrl;
    video.style.display = 'none';
    btnFoto.style.display = 'none';
    
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
};

// ========================================
// FUNCIONALIDAD DEL MODAL DE DIRECCIÓN
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    
    // Botón para abrir modal de dirección
    const btnAbrirDireccion = document.getElementById('btnAbrirDireccion');
    if (btnAbrirDireccion) {
        btnAbrirDireccion.addEventListener('click', function() {
            const modal = new bootstrap.Modal(document.getElementById('modalDireccion'));
            modal.show();
        });
    }
    
    // Variables del modal
    const modalCpInput = document.getElementById('modal_codigo_postal');
    const modalColoniaSelect = document.getElementById('modal_colonia');
    const modalMunicipioInput = document.getElementById('modal_municipio');
    const modalEstadoInput = document.getElementById('modal_estado');
    const modalCpStatus = document.getElementById('modal_cp_status');
    
    let timeoutId;
    
    // Autocompletado por código postal
    if (modalCpInput) {
        modalCpInput.addEventListener('input', function() {
            const cp = this.value.replace(/\D/g, ''); // Solo números
            this.value = cp;
            
            // Limpiar campos
            modalColoniaSelect.innerHTML = '<option value="">Primero ingresa el CP</option>';
            modalColoniaSelect.disabled = true;
            modalMunicipioInput.value = '';
            modalEstadoInput.value = '';
            modalCpStatus.textContent = 'Ingresa 5 dígitos';
            modalCpStatus.className = 'text-muted';
            
            // Cancelar búsqueda anterior
            clearTimeout(timeoutId);
            
            if (cp.length === 5) {
                modalCpStatus.textContent = 'Consultando...';
                modalCpStatus.className = 'text-info';
                
                // Esperar 500ms antes de hacer la consulta
                timeoutId = setTimeout(() => {
                    buscarColoniasPorCP(cp);
                }, 500);
            }
        });
    }
    
    // Función para buscar colonias por CP
    async function buscarColoniasPorCP(cp) {
        try {
            const response = await fetch(`/clientes/api/colonias/${cp}`);
            const data = await response.json();
            
            if (data.success) {
                // Llenar estado y municipio
                modalEstadoInput.value = data.estado;
                modalMunicipioInput.value = data.municipio;
                
                // Llenar select de colonias
                modalColoniaSelect.innerHTML = '<option value="">Selecciona una colonia</option>';
                
                data.colonias.forEach(colonia => {
                    const option = document.createElement('option');
                    option.value = colonia;
                    option.textContent = colonia;
                    modalColoniaSelect.appendChild(option);
                });
                
                modalColoniaSelect.disabled = false;
                modalCpStatus.textContent = `${data.colonias.length} colonias encontradas`;
                modalCpStatus.className = 'text-success';
                
            } else {
                modalCpStatus.textContent = 'CP no encontrado - Llena manualmente';
                modalCpStatus.className = 'text-warning';
                habilitarLlenadoManual();
            }
            
        } catch (error) {
            console.error('Error:', error);
            modalCpStatus.textContent = 'Error de conexión - Llena manualmente';
            modalCpStatus.className = 'text-danger';
            habilitarLlenadoManual();
        }
    }
    
    // Función para habilitar llenado manual
    function habilitarLlenadoManual() {
        modalMunicipioInput.removeAttribute('readonly');
        modalEstadoInput.removeAttribute('readonly');
        modalColoniaSelect.disabled = false;
        
        // Convertir select a input para llenado manual
        const parent = modalColoniaSelect.parentNode;
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control';
        input.id = 'modal_colonia';
        input.required = true;
        input.placeholder = 'Escribe el nombre de la colonia';
        
        parent.replaceChild(input, modalColoniaSelect);
    }
    
    // Guardar dirección desde el modal
    const btnGuardarDireccion = document.getElementById('btnGuardarDireccion');
    if (btnGuardarDireccion) {
        btnGuardarDireccion.addEventListener('click', function() {
            const calle = document.getElementById('modal_calle').value.trim();
            const entreCalles = document.getElementById('modal_entre_calles').value.trim();
            const numeroExterior = document.getElementById('modal_numero_exterior').value.trim();
            const numeroInterior = document.getElementById('modal_numero_interior').value.trim();
            const colonia = document.getElementById('modal_colonia').value.trim();
            const codigoPostal = document.getElementById('modal_codigo_postal').value.trim();
            const municipio = document.getElementById('modal_municipio').value.trim();
            const estado = document.getElementById('modal_estado').value.trim();
            
            // Validar campos obligatorios
            if (!calle || !numeroExterior || !colonia || !codigoPostal || !municipio || !estado) {
                alert('Por favor, completa todos los campos obligatorios de la dirección.');
                return;
            }
            
            // Guardar en campos ocultos
            document.getElementById('hidden_calle').value = calle;
            document.getElementById('hidden_entre_calles').value = entreCalles;
            document.getElementById('hidden_numero_exterior').value = numeroExterior;
            document.getElementById('hidden_numero_interior').value = numeroInterior;
            document.getElementById('hidden_colonia').value = colonia;
            document.getElementById('hidden_codigo_postal').value = codigoPostal;
            document.getElementById('hidden_municipio').value = municipio;
            document.getElementById('hidden_estado').value = estado;
            
            // Mostrar resumen en el formulario principal
            let direccionTexto = `${calle}${entreCalles ? ' (entre ' + entreCalles + ')' : ''} ${numeroExterior}${numeroInterior ? ', Int. ' + numeroInterior : ''}, ${colonia}, CP ${codigoPostal}, ${municipio}, ${estado}`;
            
            document.getElementById('direccionCompleta').textContent = direccionTexto;
            document.getElementById('resumenDireccion').style.display = 'block';
            document.getElementById('estadoDireccion').textContent = 'Dirección capturada';
            document.getElementById('estadoDireccion').className = 'badge bg-success';
            
            direccionCompleta = true;
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalDireccion'));
            modal.hide();
        });
    }
});

// ========================================
// VALIDACIÓN Y ENVÍO DEL FORMULARIO
// ========================================

document.getElementById('formNuevoCliente').addEventListener('submit', function (e) {
    e.preventDefault();
    
    // Validar dirección
    if (!direccionCompleta) {
        alert('Por favor, ingresa la dirección del cliente antes de guardar.');
        return false;
    }
    
    // Validar archivos
    if (archivosSeleccionados.length === 0) {
        alert('Debes subir al menos un documento.');
        return false;
    }
    
    const form = e.target;
    
    // Deshabilitar botón y mostrar spinner
    const btn = document.getElementById('btn-guardar-cliente');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';
    }
    
    // Preparar FormData
    const formData = new FormData(form);
    archivosSeleccionados.forEach((item, idx) => {
        formData.append('documentos', item.file);
        formData.append(`tipo_documento_${idx}`, item.tipo);
    });
    
    // Enviar formulario
    fetch(form.action, {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            response.text().then(html => {
                document.body.innerHTML = html;
            });
        }
    }).catch(error => {
        console.error('Error:', error);
        alert('Error al enviar el formulario. Por favor, intenta de nuevo.');
        
        // Rehabilitar botón
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-save"></i> Guardar';
        }
    });
});