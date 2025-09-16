function renderChartFromCanvas(canvasId, type = 'bar') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const labels = JSON.parse(canvas.dataset.labels || '[]');
  const values = JSON.parse(canvas.dataset.values || '[]');
  if (!labels.length) return;
  new Chart(canvas.getContext('2d'), {
    type,
    data: {
      labels,
      datasets: [
        {
          label: 'Total',
          data: values,
          backgroundColor: '#19875488',
          borderColor: '#198754',
          borderWidth: 1,
        },
      ],
    },
  });
}

document.addEventListener('DOMContentLoaded', () => {
  renderChartFromCanvas('chartVendasHora', 'line');
  renderChartFromCanvas('chartProdutos');
  renderChartFromCanvas('chartHoras', 'line');

  const addItemButton = document.getElementById('addItem');
  const itemsContainer = document.getElementById('itemsContainer');
  if (addItemButton && itemsContainer) {
    addItemButton.addEventListener('click', () => {
      const index = itemsContainer.querySelectorAll('.item-row').length;
      const template = document.createElement('div');
      template.classList.add('row', 'g-2', 'align-items-end', 'item-row', 'mt-2');
      template.innerHTML = `
        <div class="col-md-4">
          <label class="form-label">Produto ID</label>
          <input class="form-control" name="items[${index}][product_id]" required />
        </div>
        <div class="col-md-3">
          <label class="form-label">Quantidade</label>
          <input class="form-control" type="number" min="1" name="items[${index}][quantity]" value="1" required />
        </div>
        <div class="col-md-3">
          <label class="form-label">Preço Unitário</label>
          <input class="form-control" type="number" step="0.01" min="0" name="items[${index}][unit_price]" required />
        </div>
        <div class="col-md-2 text-end">
          <button class="btn btn-outline-danger remove-item" type="button">Remover</button>
        </div>
      `;
      itemsContainer.appendChild(template);
    });
    itemsContainer.addEventListener('click', (event) => {
      if (event.target.matches('.remove-item')) {
        const row = event.target.closest('.item-row');
        if (row) {
          row.remove();
        }
      }
    });
  }
});
