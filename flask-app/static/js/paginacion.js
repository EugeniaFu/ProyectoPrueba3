document.addEventListener("DOMContentLoaded", function () {
    const rowsPerPage = 8;
    const table = document.getElementById("tablaRentas");
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const totalPages = Math.ceil(rows.length / rowsPerPage);
    const paginationContainer = document.getElementById("pagination-container");

    function showPage(page) {
      const start = (page - 1) * rowsPerPage;
      const end = start + rowsPerPage;

      rows.forEach((row, i) => {
        row.style.display = i >= start && i < end ? "" : "none";
      });

      // Marcar el botón activo
      Array.from(paginationContainer.querySelectorAll("li.page-item")).forEach((btn, index) => {
        btn.classList.toggle("active", index === page);
      });
    }

    function createPaginationButtons() {
      const ul = document.createElement("ul");
      ul.className = "pagination";

      // Botón anterior
      const prevBtn = document.createElement("li");
      prevBtn.className = "page-item";
      prevBtn.innerHTML = `<a class="page-link" href="#">&laquo;</a>`;
      ul.appendChild(prevBtn);

      for (let i = 1; i <= totalPages; i++) {
        const li = document.createElement("li");
        li.className = "page-item";
        li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
        li.addEventListener("click", () => {
          showPage(i);
        });
        ul.appendChild(li);
      }

      // Botón siguiente
      const nextBtn = document.createElement("li");
      nextBtn.className = "page-item";
      nextBtn.innerHTML = `<a class="page-link" href="#">&raquo;</a>`;
      ul.appendChild(nextBtn);

      paginationContainer.appendChild(ul);

      // Evento para anterior y siguiente
      prevBtn.addEventListener("click", () => {
        const currentPage = ul.querySelector("li.active a")?.innerText || 1;
        if (currentPage > 1) showPage(parseInt(currentPage) - 1);
      });

      nextBtn.addEventListener("click", () => {
        const currentPage = ul.querySelector("li.active a")?.innerText || 1;
        if (currentPage < totalPages) showPage(parseInt(currentPage) + 1);
      });
    }

    if (rows.length > rowsPerPage) {
      createPaginationButtons();
      showPage(1);
    }
  });