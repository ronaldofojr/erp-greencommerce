function formatCurrency(value) {
  const number = Number(value) || 0;
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function buildAlert(message, type = 'info') {
  return `
    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Fechar"></button>
    </div>
  `;
}

document.addEventListener('DOMContentLoaded', () => {
  const appRoot = document.getElementById('pdvApp');
  if (!appRoot) return;

  const codeInput = document.getElementById('codigoProduto');
  const quantityInput = document.getElementById('quantidadeProduto');
  const discountInput = document.getElementById('descontoProduto');
  const sessionInput = document.getElementById('pdvSessionId');
  const itemsBody = document.querySelector('#pdvItens tbody');
  const feedbackBox = document.getElementById('pdvFeedback');
  const nfceBox = document.getElementById('nfceResultado');

  const totalsElements = {
    items: document.getElementById('totalItens'),
    quantity: document.getElementById('quantidadeItens'),
    subtotal: document.getElementById('subtotalVenda'),
    discount: document.getElementById('descontoVenda'),
    total: document.getElementById('totalVenda'),
  };

  const state = {
    session: null,
    items: [],
    totals: {},
  };

  function parseInitialData() {
    try {
      state.session = JSON.parse(appRoot.dataset.session || 'null');
      state.items = JSON.parse(appRoot.dataset.items || '[]');
      state.totals = JSON.parse(appRoot.dataset.totals || '{}');
    } catch (error) {
      console.error('Falha ao carregar dados iniciais do PDV', error);
    }
    applyState({});
  }

  function applyState(data) {
    if (data.session) {
      state.session = data.session;
    }
    if (Array.isArray(data.items)) {
      state.items = data.items;
    }
    if (data.totals) {
      state.totals = data.totals;
    }
    if (state.session && sessionInput) {
      sessionInput.value = state.session.id || '';
    }
    renderItems();
    updateTotals();
    focusScanner();
  }

  function renderItems() {
    if (!itemsBody) return;
    itemsBody.innerHTML = '';
    state.items.forEach((item, index) => {
      const row = document.createElement('tr');
      row.dataset.itemId = item.id;
      row.innerHTML = `
        <td>${index + 1}</td>
        <td>${item.product_code || item.product_id}</td>
        <td>${item.product_name || ''}</td>
        <td class="text-center">
          <input type="number" min="1" class="form-control form-control-sm item-quantity" value="${item.quantity}" />
        </td>
        <td class="text-end">${formatCurrency(item.unit_price)}</td>
        <td class="text-end">
          <input type="number" min="0" step="0.01" class="form-control form-control-sm text-end item-discount" value="${Number(item.discount || 0).toFixed(2)}" />
        </td>
        <td class="text-end">${formatCurrency(item.total)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm" role="group">
            <button type="button" class="btn btn-outline-primary atualizar-item">Atualizar</button>
            <button type="button" class="btn btn-outline-danger remover-item">Remover</button>
          </div>
        </td>
      `;
      itemsBody.appendChild(row);
    });
  }

  function updateTotals() {
    const totals = state.totals || {};
    if (totalsElements.items) totalsElements.items.textContent = totals.items ?? state.items.length;
    if (totalsElements.quantity) totalsElements.quantity.textContent = totals.quantity ?? 0;
    if (totalsElements.subtotal) totalsElements.subtotal.textContent = formatCurrency(totals.subtotal ?? 0);
    if (totalsElements.discount) totalsElements.discount.textContent = formatCurrency(totals.discount ?? 0);
    if (totalsElements.total) totalsElements.total.textContent = formatCurrency(totals.total ?? 0);
  }

  function focusScanner() {
    if (codeInput) {
      setTimeout(() => codeInput.focus(), 100);
    }
  }

  function resetItemForm() {
    if (codeInput) codeInput.value = '';
    if (quantityInput) quantityInput.value = '1';
    if (discountInput) discountInput.value = '';
  }

  function showFeedback(message, type = 'info') {
    if (!feedbackBox) return;
    feedbackBox.innerHTML = buildAlert(message, type);
  }

  function clearFeedback() {
    if (feedbackBox) feedbackBox.innerHTML = '';
  }

  function clearNfceBox() {
    if (nfceBox) nfceBox.innerHTML = '';
  }

  async function fetchJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || 'Erro ao comunicar com o servidor');
    }
    return data;
  }

  async function handleAddItem(event) {
    event.preventDefault();
    if (!sessionInput || !codeInput || !quantityInput) return;
    const code = codeInput.value.trim();
    if (!code) {
      showFeedback('Informe o código do produto para adicionar itens.', 'warning');
      focusScanner();
      return;
    }
    const quantity = Number(quantityInput.value) || 1;
    const discountValue = discountInput && discountInput.value !== '' ? Number(discountInput.value) : null;

    try {
      const payload = {
        session_id: sessionInput.value ? Number(sessionInput.value) : undefined,
        code,
        quantity,
      };
      if (discountValue !== null && !Number.isNaN(discountValue)) {
        payload.discount = discountValue;
      }
      const data = await fetchJson('/pdv/add-item', payload);
      clearFeedback();
      applyState(data);
      resetItemForm();
      clearNfceBox();
    } catch (error) {
      showFeedback(error.message, 'danger');
    }
  }

  async function handleUpdateItem(row) {
    const quantityField = row.querySelector('.item-quantity');
    const discountField = row.querySelector('.item-discount');
    const quantity = Number(quantityField?.value || 0);
    const discountRaw = discountField?.value ?? '';
    const discount = discountRaw === '' ? null : Number(discountRaw);

    try {
      const data = await fetchJson('/pdv/update-item', {
        session_id: Number(sessionInput.value),
        item_id: Number(row.dataset.itemId),
        quantity,
        discount: discount,
      });
      applyState(data);
      clearFeedback();
    } catch (error) {
      showFeedback(error.message, 'danger');
    }
  }

  async function handleRemoveItem(row) {
    try {
      const data = await fetchJson('/pdv/remove-item', {
        session_id: Number(sessionInput.value),
        item_id: Number(row.dataset.itemId),
      });
      applyState(data);
      clearFeedback();
    } catch (error) {
      showFeedback(error.message, 'danger');
    }
  }

  async function handleFinalize(event) {
    event.preventDefault();
    if (!sessionInput) return;
    const submitter = event.submitter;
    const emitir = submitter?.dataset?.emitir === 'true';
    const form = event.target;
    const paymentMethod = form.payment_method?.value || form.querySelector('[name="payment_method"]').value;
    const customerField = form.customer_id || form.querySelector('[name="customer_id"]');
    const customerId = customerField?.value ? Number(customerField.value) : null;
    const contingencia = Boolean(form.contingencia?.checked);

    try {
      const payload = {
        session_id: Number(sessionInput.value),
        payment_method: paymentMethod,
        emitir_nfce: emitir,
        contingencia,
      };
      if (customerId) {
        payload.customer_id = customerId;
      }
      const data = await fetchJson('/pdv/finalizar-venda', payload);
      showFeedback(data.message || `Venda ${data.sale_id} finalizada com sucesso.`, 'success');
      if (nfceBox) {
        if (data.nfce) {
          nfceBox.innerHTML = buildAlert(
            `NFC-e ${data.nfce.status}. DANFE: ${data.nfce.danfe_path}. QRCode: <a href="${data.nfce.qrcode_url}" target="_blank" rel="noopener">${data.nfce.qrcode_url}</a>`,
            'info',
          );
        } else {
          nfceBox.innerHTML = '';
        }
      }
      if (data.next_session) {
        applyState(data.next_session);
      }
      form.reset();
      if (form.payment_method) form.payment_method.value = 'dinheiro';
    } catch (error) {
      showFeedback(error.message, 'danger');
    }
  }

  document.getElementById('formAdicionarItem')?.addEventListener('submit', handleAddItem);

  if (codeInput) {
    codeInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        handleAddItem(event);
      }
    });
  }

  itemsBody?.addEventListener('click', (event) => {
    const actionButton = event.target.closest('button');
    if (!actionButton) return;
    const row = actionButton.closest('tr');
    if (!row) return;

    if (actionButton.classList.contains('atualizar-item')) {
      handleUpdateItem(row);
    }
    if (actionButton.classList.contains('remover-item')) {
      handleRemoveItem(row);
    }
  });

  document.getElementById('finalizarVendaForm')?.addEventListener('submit', handleFinalize);

  parseInitialData();
});
