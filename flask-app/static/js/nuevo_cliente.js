// Elimina el primer bloque duplicado de vista previa (solo deja la lógica avanzada)
let archivosSeleccionados = [];

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

document.getElementById('formNuevoCliente').addEventListener('submit', function (e) {
    if (archivosSeleccionados.length === 0) {
        alert('Debes subir al menos un documento.');
        e.preventDefault();
        return;
    }
    const form = e.target;
    const formData = new FormData(form);
    archivosSeleccionados.forEach((item, idx) => {
        formData.append('documentos', item.file);
        formData.append(`tipo_documento_${idx}`, item.tipo);
    });

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
    });
    e.preventDefault();
});