# GreenCommerce ERP (MVP NFC-e RJ)

ERP modular em Flask para pequenos comércios, restaurantes e lojas do Rio de Janeiro, com foco em NFC-e (Nota Fiscal de Consumidor Eletrônica), integrações de PDV, PIX e controles financeiros básicos. O código está estruturado para expansão para outros estados (ex.: SP, SC) via `app/config_fiscal.py`.

## Tecnologias principais

- **Backend**: Python 3 + Flask
- **Banco**: SQLite (arquivo `db/erp.db`)
- **Frontend**: HTML + Bootstrap 5 + Chart.js
- **Fiscal**: geração de XML NFC-e, assinatura (mock), DANFE em PDF (`reportlab`), integração SEFAZ-RJ/SVRS
- **Pagamentos**: QR Code PIX (`qrcode`), mock Banco Central

## Estrutura de pastas

```
app/
  __init__.py
  app.py (entry no diretório raiz)
  database.py
  estoque.py
  vendas.py
  pdv.py
  nfce.py
  pagamentos.py
  comandas.py
  financas.py
  clientes.py
  relatorios.py
  security.py
  utils.py
  config_fiscal.py
backups/
  (XMLs/DANFEs gerados)
db/
  erp.db (SQLite)
scripts/
  init_db.py (popular dados fictícios)
templates/
  *.html (Bootstrap)
static/
  css/styles.css
  js/main.js
  js/pdv.js
```

## Instalação e execução

1. **Criar ambiente virtual e instalar dependências:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install flask qrcode reportlab signxml pynfe openpyxl werkzeug
   ```

   > Durante homologação é possível usar certificados falsos; para produção configure certificado A1 válido.

2. **Popular banco com dados fictícios (opcional, gera produtos, clientes e NFC-e de exemplo):**

   ```bash
   python scripts/init_db.py
   ```

3. **Executar o servidor Flask:**

   ```bash
   export FLASK_APP=app.py
   flask run --reload
   ```

   A aplicação ficará disponível em `http://127.0.0.1:5000/`.

4. **Acesso inicial:**

   - Usuário admin: `admin` / `admin123`
   - Usuário caixa: `caixa` / `caixa123`

## Configuração fiscal (wizard)

1. Acesse `/onboarding` e informe CNPJ, IE, CSC ID/token fornecidos pela SEFAZ-RJ.
2. Informe caminho do certificado digital A1 (arquivo `.pfx`) e senha. Em ambiente de teste é possível deixar em branco (assinatura mock).
3. Defina ambiente (`homologacao` ou `producao`) e UF padrão (`RJ`). Para adicionar estados extras, atualize `app/config_fiscal.py` com URLs e regras do autorizador.
4. Após salvar, as NFC-e emitidas são gravadas em `backups/nfce_<id>.xml` e DANFE em PDF com QR Code e contato do Procon-RJ (151).

## Fluxos principais

### Cadastro de produtos e estoque
- Página **Produtos**: formulário Bootstrap com campos fiscais (NCM, CEST, CFOP, alíquota ICMS).
- Tabela `inventory_movements` registra ajustes automáticos após vendas autorizadas.
- Alerta de estoque baixo (`< 10 unidades`) exibido no dashboard.

### Vendas, PDV e promoções
- Página **PDV** (`/pdv`): layout estilo frente de caixa com entrada focada para leitores de código de barras (tratados como teclado), tabela dinâmica de itens, totalizador em tempo real e botões para finalizar venda ou emitir NFC-e imediatamente.
- Funções REST do PDV: `GET /pdv/session`, `POST /pdv/add-item`, `POST /pdv/update-item`, `POST /pdv/remove-item`, `POST /pdv/finalizar-venda` (gera venda, registra pagamento e pode emitir NFC-e).
- Página **Vendas**: modal para registrar vendas com múltiplos itens.
- Promoção automática: 10% de desconto em compras acima de R$ 100.
- Formas de pagamento: dinheiro, cartão, PIX (gera QR Code).
- Relatórios diários com Chart.js (ticket médio, produtos mais vendidos, vendas por hora).

### PDV web (scanner e finalização)
- Campo de código fica em foco automático e aceita leitura de scanners USB/HID (evento `Enter` dispara busca do produto).
- Tabela exibe colunas N°, Código, Produto, Quantidade, Valor, Desconto e Total, com botões para atualizar/remover itens.
- Totalizador lateral mostra subtotal, descontos acumulados, quantidade total e total final da venda.
- Formulário de finalização permite escolher forma de pagamento (dinheiro/cartão/PIX), marcar contingência SVRS e emitir NFC-e imediatamente.
- Após finalizar, uma nova sessão do PDV é criada automaticamente para acelerar o próximo atendimento.

### Finanças
- Controle de contas a pagar/receber (`accounts_payable`, `accounts_receivable`).
- Relatório básico de fluxo de caixa em `/financas/fluxo-caixa` (restrito a `admin`/`gerente`).

### NFC-e (RJ)
- `POST /emitir-nfce`: gera XML, assina (mock via `signxml` se configurado), envia a SEFAZ-RJ ou SVRS, gera DANFE (PDF com `reportlab`).
- Contingência: parâmetro `contingencia=true` salva XML localmente para envio posterior.
- Cancelamento: `POST /cancelar-nfce` até 24h (registra evento em `nfce_events`).
- Armazenamento de XML por 5 anos (pasta `backups/`, controle em tabela `backups`).
- Notificação: log `log_audit` pode ser estendido para e-mail/WhatsApp (mock Twilio).

### Restaurantes e delivery
- `POST /abrir-comanda`: cria comanda/mesa.
- `POST /importar-pedido-ifood`: mock para pedidos iFood (gera comanda e pedidos).
- Workflow de status: recebido → em preparo → entregue (`comandas.update_order_status`).

### Lojas e clientes
- Cadastro de clientes com CPF opcional para NFC-e (validação simples, LGPD: checkbox de consentimento).
- Histórico de compras disponível via `clientes.customer_history`.

### Pagamentos PIX
- `POST /gerar-pix`: gera QR Code (arquivo em `static/img/pix_<txid>.png`) e registra pagamento pendente.
- `pagamentos.mock_pix_callback(txid)`: simula confirmação do Banco Central.

### Relatórios fiscais
- `/relatorios/vendas`: dashboard analítico (produtos, ticket médio, vendas por hora).
- `/relatorios/sped`: exporta NFC-e emitidas para layout texto básico SPED (somente `admin`/`gerente`).
- `/backup/nfce`: lista XMLs armazenados.

## Exemplos de chamadas API

### Criar produto (REST)
```bash
curl -X POST http://localhost:5000/produtos \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Cafe Mocha",
        "code": "CAFE999",
        "price": 12.5,
        "quantity": 20,
        "ncm": "09012100",
        "cest": "0300400",
        "cfop": "5102",
        "icms_aliquota": 18
      }'
```

### Fluxo PDV (REST)
```bash
# Adicionar item pelo código
curl -X POST http://localhost:5000/pdv/add-item \
  -H 'Content-Type: application/json' \
  -d '{"code": "CAFE001", "quantity": 1}'

# Atualizar quantidade/desconto de um item temporário
curl -X POST http://localhost:5000/pdv/update-item \
  -H 'Content-Type: application/json' \
  -d '{"session_id": 1, "item_id": 2, "quantity": 3, "discount": 1.50}'

# Finalizar a venda e emitir NFC-e
curl -X POST http://localhost:5000/pdv/finalizar-venda \
  -H 'Content-Type: application/json' \
  -d '{"session_id": 1, "payment_method": "pix", "emitir_nfce": true}'
```

### Registrar venda e emitir NFC-e
```bash
# Registrar venda
curl -X POST http://localhost:5000/vendas \
  -H 'Content-Type: application/json' \
  -d '{
        "items": [
          {"product_id": 1, "quantity": 2, "unit_price": 6.0},
          {"product_id": 3, "quantity": 1, "unit_price": 28.0}
        ],
        "payment_method": "pix"
      }'

# Emissão da NFC-e
curl -X POST http://localhost:5000/emitir-nfce \
  -H 'Content-Type: application/json' \
  -d '{"sale_id": 1}'
```

### Gerar QR Code PIX
```bash
curl -X POST http://localhost:5000/gerar-pix \
  -H 'Content-Type: application/json' \
  -d '{"sale_id": 1, "amount": 120.00, "description": "Pedido 1"}'
```

### Importar pedido iFood (mock)
```bash
curl -X POST http://localhost:5000/importar-pedido-ifood \
  -H 'Content-Type: application/json' \
  -d '{
        "order_id": "IFOOD123",
        "items": [
          {"product_id": 3, "description": "Hambúrguer", "quantity": 1, "unit_price": 28.0},
          {"product_id": 1, "description": "Café", "quantity": 1, "unit_price": 6.0}
        ]
      }'
```

## Segurança e LGPD
- Autenticação básica via `werkzeug.security` (hash de senha).
- Roles: `admin`, `gerente`, `caixa`. Rotas críticas usam decorator `require_role`.
- Validação de CNPJ/CPF/IE simplificada (regex) com opção de integrar API Receita Federal.
- Logs de auditoria via `app.utils.log_audit` (extensível para SIEM).

## Roadmap / expansão sugerida
- Multiempresa (schema com `tenant_id`).
- Integração NFSe (Prefeitura RJ) e SAT SP.
- Integração e-commerce (Mercado Livre, Shopify) com sincronização de estoque.
- Upload automático de XML para AWS S3/GCP Storage.
- Automação de testes (`pytest`, `pytest-flask`).
- Motor de promoções avançado e fidelidade.
- Monitor fiscal 2025/2026 (API mock já prevista em `config_fiscal`).
- Integração com leitores de código de barras USB/serial com configuração de prefixo/sufixo.

## Licença
Uso interno para MVP. Ajuste conforme necessidades do cliente.
