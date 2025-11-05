# Guia Completo de Scraping de Tribunais Brasileiros

## Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura dos Portais](#arquitetura-dos-portais)
3. [Estratégias Anti-Bot](#estratégias-anti-bot)
4. [Padrões de Iframe](#padrões-de-iframe)
5. [Timing e Performance](#timing-e-performance)
6. [Extração de Dados](#extração-de-dados)
7. [Troubleshooting](#troubleshooting)
8. [Checklist para Novos Tribunais](#checklist-para-novos-tribunais)

---

## Visão Geral

### Tribunais Implementados

| Tribunal | Tecnologia | Iframe | Anti-Bot | Tempo Médio | Dificuldade |
|----------|-----------|---------|----------|-------------|-------------|
| **TJSP** | Angular SPA | ❌ Não | ⚠️ Médio | ~30s | Média |
| **PJE (TRF1)** | JSF/PrimeFaces | ❌ Não | ✅ Alto | ~45s | Alta |
| **TJRJ** | Angular SPA | ✅ Sim (nested) | ✅ Muito Alto | ~90s | Muito Alta |

### Stack Tecnológica Comum

```python
# Bibliotecas principais
- Playwright (async_api) - Browser automation
- BeautifulSoup4 - HTML parsing (backup)
- FastAPI - API endpoints
- Pydantic - Data validation
```

---

## Arquitetura dos Portais

### Tipo 1: Angular SPA Direto (TJSP)

**Características:**
- Aplicação Angular renderizada diretamente na página
- Hash routing (`#/consultapublica`)
- Componentes Angular visíveis no DOM
- Navegação client-side

**Estrutura HTML:**
```html
<app-root>
  <app-consulta-processual>
    <form>
      <!-- Formulários de busca -->
    </form>
    <div class="results">
      <!-- Resultados aparecem aqui -->
    </div>
  </app-consulta-processual>
</app-root>
```

**Navegação:**
```python
await page.goto("https://esaj.tjsp.jus.br/cjsg/consultaCompleta.do")
# Aguardar Angular bootstrapping
await page.wait_for_selector("app-root", state="attached")
```

**Prós:**
- Mais rápido (sem iframe overhead)
- Seletores diretos
- Debugging mais fácil

**Contras:**
- Anti-bot pode bloquear completamente
- Precisa aguardar Angular compilar

---

### Tipo 2: JSF/PrimeFaces Tradicional (PJE)

**Características:**
- Server-side rendering com AJAX
- ViewState e tokens CSRF
- PrimeFaces components
- DataTables dinâmicas

**Estrutura HTML:**
```html
<form id="fPP:searchProcessos">
  <input type="hidden" name="javax.faces.ViewState" value="..." />

  <!-- PrimeFaces DataTable -->
  <div class="ui-datatable">
    <table>
      <tbody id="fPP:searchProcessos:processosTable_data">
        <!-- Linhas renderizadas via AJAX -->
      </tbody>
    </table>
  </div>
</form>
```

**Navegação:**
```python
# Login primeiro (se necessário)
await page.goto("https://pje1g.trf1.jus.br/consultapublica/ConsultaPublica/listView.seam")

# Aguardar PrimeFaces carregar
await page.wait_for_selector(".ui-datatable", timeout=30000)
```

**Prós:**
- Estrutura mais estável
- Menos mudanças entre versões

**Contras:**
- AJAX complexo para paginar
- ViewState precisa ser preservado
- Múltiplas requisições HTTP

---

### Tipo 3: Angular SPA em Iframe Aninhado (TJRJ)

**Características:**
- **Nested iframe** - Angular dentro de iframe
- Duplo bootstrapping (página + iframe)
- Anti-bot muito agressivo
- Componentes custom Angular

**Estrutura HTML:**
```html
<!-- Página externa -->
<app-root>
  <app-consultar>
    <!-- Iframe dinâmico criado por Angular -->
    <iframe id="mainframe" src="https://www3.tjrj.jus.br/consultaprocessual/#/conspublica">
      <!-- DENTRO DO IFRAME -->
      <app-root>
        <app-consulta-publica>
          <div class="texto-link">
            <b>Processo:</b> 0000927-15.2024.8.19.0003
          </div>
        </app-consulta-publica>
      </app-root>
    </iframe>
  </app-consultar>
</app-root>
```

**Navegação (CRÍTICO):**
```python
# 1. Navegar para página externa
await page.goto("https://www3.tjrj.jus.br/consultaprocessual/#/consultapublica")

# 2. Aguardar Angular externo
await page.wait_for_selector("app-consulta-publica", state="attached")

# 3. AGUARDAR IFRAME SER CRIADO (pode demorar!)
await page.wait_for_selector("#mainframe", timeout=30000, state="attached")

# 4. SWITCH DE CONTEXTO - CRUCIAL!
iframe_element = await page.query_selector("#mainframe")
frame = await iframe_element.content_frame()

# 5. Agora usar 'frame' ao invés de 'page'
await frame.click("text=Por Nome")
```

**⚠️ ARMADILHA COMUM:**
```python
# ❌ ERRADO - Continua usando page
await page.fill("#nomeParte", "Claro")

# ✅ CORRETO - Usa frame
await frame.fill("#nomeParte", "Claro")
```

**Prós:**
- Isolamento de contexto
- Pode ter múltiplos iframes

**Contras:**
- **Muito mais lento** (dobro do tempo)
- Switch de contexto complexo
- Debugging difícil
- Anti-bot detecta facilmente

---

## Estratégias Anti-Bot

### Nível 1: Anti-Bot Básico (TJSP)

**Sinais que detectam:**
- `navigator.webdriver === true`
- Ausência de `window.chrome`
- User-Agent suspeito

**Contramedidas:**
```python
# 1. Desabilitar flags de automação
browser = await playwright.chromium.launch(
    headless=True,
    args=[
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
    ]
)

# 2. Context com user-agent real
context = await browser.new_context(
    locale="pt-BR",
    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    viewport={"width": 1366, "height": 768},
)

# 3. Injetar scripts anti-detecção
await context.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
""")
```

---

### Nível 2: Anti-Bot Avançado (PJE)

**Detecção adicional:**
- Padrões de timing
- Mouse movements
- Velocidade de digitação

**Contramedidas adicionais:**
```python
# 4. Random delays humanos
import random

await asyncio.sleep(random.uniform(1.0, 2.5))

# 5. Digitação humana (não usar fill diretamente)
async def human_type(page, selector, text):
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))

# 6. Movimentos de mouse
await page.mouse.move(
    random.randint(100, 500),
    random.randint(100, 500)
)
```

---

### Nível 3: Anti-Bot Muito Agressivo (TJRJ)

**Comportamento observado:**
- Tela branca se detectar bot
- Iframe não carrega
- Timeout em `wait_for_selector`

**Mensagem do usuário:**
> "eles botao tipo uma tela na frente que deixa em branco, quando detecta bot... NAO EH TIMEOUT, se nao abrir logo, é erro de bot"

**Contramedidas TJRJ-specific:**
```python
# 7. Todos os anteriores +

# 8. Stealth mode completo
await context.add_init_script("""
    // Permissions API
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );

    // Plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // Languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['pt-BR', 'pt', 'en-US', 'en']
    });
""")

# 9. Aguardar MUITO mais - Angular + anti-bot delays
await asyncio.sleep(random.uniform(2.0, 4.0))

# 10. Network idle é CRUCIAL
await page.goto(url, wait_until="networkidle", timeout=30000)
```

**🔴 Se ainda assim não funcionar:**
```python
# Último recurso: headless=False + XVFB
browser = await playwright.chromium.launch(
    headless=False,  # Mais difícil de detectar
    # Usar Xvfb no servidor
)
```

---

## Padrões de Iframe

### Como Detectar se Tem Iframe

**1. Inspecionar página manualmente:**
```bash
curl -s "https://portal.tribunal.com" | grep -i iframe
```

**2. Via Playwright:**
```python
# Listar todos os frames
frames = page.frames
print(f"Total frames: {len(frames)}")
for frame in frames:
    print(f"Frame URL: {frame.url}")
```

**3. Via DevTools:**
```javascript
// No console do browser
document.querySelectorAll('iframe').length
```

---

### Padrão: Iframe Estático (simples)

```html
<!-- Iframe já existe no HTML inicial -->
<iframe id="conteudo" src="https://sistema.tribunal.com/consulta">
```

**Handling:**
```python
# Aguardar iframe estar presente
await page.wait_for_selector("#conteudo")

# Get frame
iframe = page.frame(name="conteudo")  # Por name
# OU
iframe = page.frame(url=lambda url: "consulta" in url)  # Por URL

# Usar frame
await iframe.fill("#busca", "texto")
```

---

### Padrão: Iframe Dinâmico (TJRJ)

```html
<!-- Iframe criado por JavaScript DEPOIS do page load -->
<app-iframe>
  <!-- Angular cria isso dinamicamente -->
  <iframe id="mainframe" src="...">
```

**Handling:**
```python
# ❌ ERRADO - iframe pode não existir ainda
iframe = page.frame("mainframe")  # Pode ser None!

# ✅ CORRETO - Aguardar criação
await page.wait_for_selector("#mainframe", state="attached", timeout=30000)

iframe_element = await page.query_selector("#mainframe")
frame = await iframe_element.content_frame()

# ⚠️ frame pode ser None se ainda não carregou!
if not frame:
    await asyncio.sleep(2)
    frame = await iframe_element.content_frame()
```

---

### Padrão: Iframe Aninhado (nested)

```html
<iframe id="externo">
  <iframe id="interno">
    <!-- Conteúdo aqui -->
  </iframe>
</iframe>
```

**Handling:**
```python
# Frame externo
outer_frame = await get_frame(page, "#externo")

# Frame interno (dentro do externo!)
inner_iframe = await outer_frame.query_selector("#interno")
inner_frame = await inner_iframe.content_frame()

# Usar inner_frame
await inner_frame.click("button")
```

---

## Timing e Performance

### Regras de Ouro

1. **Sempre use `wait_for_selector` ao invés de sleep fixo**
   ```python
   # ❌ Ruim
   await asyncio.sleep(5)
   await page.click("button")

   # ✅ Bom
   await page.wait_for_selector("button", state="visible", timeout=10000)
   await page.click("button")
   ```

2. **Combine wait_for com timeout**
   ```python
   try:
       await page.wait_for_selector(".results", timeout=15000)
   except PlaywrightTimeoutError:
       # Continua anyway ou lança erro
       pass
   ```

3. **Network idle é seu amigo**
   ```python
   await page.goto(url, wait_until="networkidle")
   ```

---

### Tempos Típicos por Tribunal

| Operação | TJSP | PJE | TJRJ | Notas |
|----------|------|-----|------|-------|
| **Browser Launch** | ~15s | ~15s | ~15s | Cache ajuda |
| **Page Load** | ~3s | ~5s | ~8s | Depende de rede |
| **Angular Bootstrap** | ~2s | N/A | ~5s | Duplo no TJRJ |
| **Form Fill** | ~1s | ~2s | ~3s | Dropdowns custom |
| **Search Execute** | ~2s | ~5s | ~3s | AJAX/fetch |
| **Results Render** | ~2s | ~3s | ~3s | Angular digest |
| **Data Extraction** | <1s | ~1s | <1s | JavaScript eval |
| **TOTAL** | ~25s | ~35s | ~90s | |

---

### Otimizações Aplicadas

**TJRJ - Antes vs Depois:**
```python
# ANTES (lento)
await asyncio.sleep(5)  # Frame load
await asyncio.sleep(2)  # Tab click
await asyncio.sleep(5)  # Form load
await asyncio.sleep(8)  # Results
# Total: 20s em sleeps

# DEPOIS (otimizado)
await asyncio.sleep(2)  # Frame load
await asyncio.sleep(1)  # Tab click
await asyncio.sleep(2)  # Form load
await asyncio.sleep(3)  # Results
# Total: 8s em sleeps (-12s!)
```

**Resultado:** 95s → 85s (11% melhoria)

---

## Extração de Dados

### Estratégia 1: JavaScript Evaluation (Preferred)

**Quando usar:**
- Dados já estão no DOM
- Estrutura previsível
- Performance crítica

**Exemplo:**
```python
extraction_script = """
() => {
    const processes = [];
    const rows = document.querySelectorAll('tr.processo');

    rows.forEach(row => {
        processes.push({
            numero: row.querySelector('.numero')?.textContent?.trim(),
            autor: row.querySelector('.autor')?.textContent?.trim(),
        });
    });

    return processes;
}
"""

result = await page.evaluate(extraction_script)
```

**Prós:**
- Muito rápido (executa no browser)
- Acesso a toda API do DOM
- Pode chamar funções JavaScript da página

**Contras:**
- Debug difícil (console.log não aparece)
- Precisa retornar dados serializáveis (JSON)

---

### Estratégia 2: BeautifulSoup (Backup)

**Quando usar:**
- Estrutura HTML complexa
- Precisa regex avançado
- Debugging necessário

**Exemplo:**
```python
from bs4 import BeautifulSoup

html = await page.content()
soup = BeautifulSoup(html, 'html.parser')

processos = []
for row in soup.find_all('tr', class_='processo'):
    processos.append({
        'numero': row.find('td', class_='numero').text.strip(),
        'autor': row.find('td', class_='autor').text.strip(),
    })
```

**Prós:**
- Debug fácil
- APIs conhecidas (find, find_all, select)
- Regex integration

**Contras:**
- Mais lento (parsing em Python)
- Precisa transferir HTML inteiro

---

### Estratégia 3: Hybrid (TJRJ)

**Melhor dos dois mundos:**

```python
# 1. JavaScript para estruturas simples
processo_count = await frame.evaluate("() => document.querySelectorAll('.texto-link').length")

# 2. Se > 0, extrair via JavaScript
if processo_count > 0:
    result = await frame.evaluate(extraction_script)
else:
    # 3. Fallback: BeautifulSoup para debug
    html = await frame.content()
    # Analisar manualmente
```

---

## Troubleshooting

### Problema: Iframe não carrega

**Sintomas:**
```python
await page.wait_for_selector("#iframe")  # Timeout!
```

**Diagnóstico:**
```python
# 1. Verificar se iframe existe
iframes = await page.query_selector_all("iframe")
print(f"Found {len(iframes)} iframes")

# 2. Ver URLs dos frames
for frame in page.frames:
    print(f"Frame: {frame.url}")

# 3. Salvar screenshot
await page.screenshot(path="/tmp/debug.png", full_page=True)

# 4. Salvar HTML
html = await page.content()
with open("/tmp/debug.html", "w") as f:
    f.write(html)
```

**Soluções:**
```python
# Opção A: Aguardar mais
await asyncio.sleep(5)

# Opção B: Aguardar networkidle
await page.goto(url, wait_until="networkidle")

# Opção C: Anti-bot mais agressivo (ver seção Anti-Bot)
```

---

### Problema: Seletores não encontrados

**Sintomas:**
```python
await frame.click("#botao")  # Elemento não encontrado
```

**Diagnóstico:**
```python
# 1. Listar elementos disponíveis
buttons = await frame.evaluate("""
    () => {
        return Array.from(document.querySelectorAll('button'))
            .map(b => ({
                id: b.id,
                class: b.className,
                text: b.textContent.trim()
            }));
    }
""")
print(buttons)

# 2. Verificar se está no frame correto
print(f"Current frame URL: {frame.url}")
```

**Soluções:**
```python
# Opção A: Usar texto ao invés de seletor
await frame.click("text=Pesquisar")

# Opção B: Seletor mais genérico
await frame.click("button:has-text('Pesquisar')")

# Opção C: JavaScript direto
await frame.evaluate("() => { document.querySelector('button').click(); }")
```

---

### Problema: Dados não extraídos

**Sintomas:**
```python
result = await frame.evaluate(script)
print(len(result))  # 0 itens!
```

**Diagnóstico:**
```python
# 1. Verificar se elementos existem
count = await frame.evaluate("() => document.querySelectorAll('.item').length")
print(f"Items in DOM: {count}")

# 2. Salvar HTML do frame
html = await frame.evaluate("() => document.body.innerHTML")
with open("/tmp/frame.html", "w") as f:
    f.write(html)

# 3. Analisar manualmente
```

**Soluções:**
```python
# Opção A: Aguardar rendering
await asyncio.sleep(3)
result = await frame.evaluate(script)

# Opção B: Aguardar elemento específico
await frame.wait_for_selector(".item", state="visible")

# Opção C: Tentar outros seletores
# Ver HTML salvo e ajustar script de extração
```

---

### Problema: Timeout 504 Gateway

**Sintomas:**
```
HTTP Request: POST http://scrapper:8080/v1/processos/tjrj/listar "HTTP/1.1 504 Gateway Timeout"
```

**Causa:**
Scraper demora mais que o timeout do cliente HTTP.

**Solução:**
```python
# No cliente HTTP (api/services/scrapper_client.py)
response = await request_with_retry(
    "POST",
    url,
    client=client,
    json=payload,
    timeout=120.0  # Aumentar para scrapers lentos
)
```

**Tempos recomendados:**
- TJSP: 60s
- PJE: 90s
- TJRJ: 120s

---

## Checklist para Novos Tribunais

### Fase 1: Reconhecimento (30min)

- [ ] **1.1 Acessar portal manualmente**
  - URL base
  - Tipo de consulta (pública, requer login?)
  - Captcha presente?

- [ ] **1.2 Identificar tecnologia**
  ```bash
  # Ver no DevTools → Network → Headers
  # Procurar por:
  - X-Powered-By
  - Server
  - Scripts carregados (angular.js, jquery, etc)
  ```

- [ ] **1.3 Verificar iframes**
  ```javascript
  // No console
  document.querySelectorAll('iframe').length
  ```

- [ ] **1.4 Testar busca manual**
  - Formulário de busca
  - Campos obrigatórios
  - Formato de entrada
  - Como resultados aparecem

---

### Fase 2: Análise Técnica (1h)

- [ ] **2.1 Inspecionar HTML**
  ```bash
  curl -s "https://portal.tribunal.com/consulta" > page.html
  grep -i "iframe\|angular\|react\|vue" page.html
  ```

- [ ] **2.2 Analisar Network**
  - APIs chamadas?
  - Autenticação necessária?
  - Tokens CSRF?
  - Rate limiting?

- [ ] **2.3 Testar anti-bot**
  ```python
  # Script simples
  async def test_bot_detection():
      browser = await playwright.chromium.launch(headless=True)
      page = await browser.new_page()
      await page.goto(url)
      await page.screenshot(path="/tmp/test.png")

      # Página branca? = Anti-bot detectou
      # Página normal? = OK
  ```

- [ ] **2.4 Mapear fluxo**
  1. Página inicial
  2. Formulário de busca
  3. Submissão
  4. Resultados
  5. Detalhe de processo

---

### Fase 3: Implementação (2-4h)

- [ ] **3.1 Criar modelos Pydantic**
  ```python
  # scrapper/api/models.py
  class ProcessoResumoXXX(BaseModel):
      numeroProcesso: str
      # ... outros campos

  class XXXProcessoQuery(BaseModel):
      nome_parte: Optional[str] = None
      # ... parâmetros de busca
  ```

- [ ] **3.2 Implementar fetcher**
  - `navigate_to_search()` - Navegação inicial
  - `submit_query()` - Preencher e submeter form
  - `extract_process_list()` - Extrair lista
  - `extract_process_detail()` - Extrair detalhes

- [ ] **3.3 Adicionar anti-bot** (copiar de TJRJ se muito agressivo)

- [ ] **3.4 Timing apropriado**
  - Começar conservador (sleeps maiores)
  - Otimizar depois de funcionar

- [ ] **3.5 Tratamento de erros**
  ```python
  try:
      await page.wait_for_selector(".results", timeout=15000)
  except PlaywrightTimeoutError:
      # Salvar debug files
      await page.screenshot(path="/tmp/error.png")
      raise HTTPException(status_code=504, detail="...")
  ```

---

### Fase 4: Integração (1h)

- [ ] **4.1 Adicionar endpoints**
  ```python
  # scrapper/api/app.py
  @app.post("/v1/processos/xxx/listar")
  async def listar_processos_xxx(payload: XXXProcessoQuery):
      return await fetch_xxx_process_list(payload)
  ```

- [ ] **4.2 Criar cliente**
  ```python
  # api/services/scrapper_client.py
  async def listar_processos_xxx(payload: Dict[str, Any]):
      client = await get_http_client()
      url = f"http://{host}:{port}/v1/processos/xxx/listar"
      response = await request_with_retry(
          "POST", url, client=client, json=payload, timeout=90.0
      )
      return response.json()
  ```

- [ ] **4.3 Adicionar router**
  ```python
  # api/routers/scrapper.py
  @router.post("/scrapper/processos/xxx/listar")
  async def listar_processos_xxx(payload: XXXProcessoQuery):
      resultado = await scrapper_client.listar_processos_xxx(...)
      return XXXProcessoListResponse.model_validate(resultado)
  ```

- [ ] **4.4 Atualizar frontend**
  ```html
  <!-- frontend/index.html -->
  <option value="XXX">XXX - Nome do Tribunal</option>
  ```

  ```javascript
  // frontend/app.js
  if (tribunal === 'XXX') {
      endpoint = '/api/v1/scrapper/processos/xxx/listar';
  }
  ```

---

### Fase 5: Testes (1h)

- [ ] **5.1 Teste unitário (scrapper isolado)**
  ```python
  async def test():
      query = XXXProcessoQuery(nome_parte="Claro")
      result = await fetch_xxx_process_list(query)
      assert len(result.processos) > 0
  ```

- [ ] **5.2 Teste via API**
  ```bash
  curl -X POST http://localhost:8000/api/v1/scrapper/processos/xxx/listar \
    -H "Content-Type: application/json" \
    -d '{"nome_parte":"Claro"}'
  ```

- [ ] **5.3 Teste via frontend**
  - Abrir http://localhost:8000
  - Selecionar tribunal XXX
  - Buscar "Claro"
  - Verificar resultados

- [ ] **5.4 Teste de carga**
  ```bash
  # 5 requisições simultâneas
  for i in {1..5}; do
    curl ... &
  done
  wait
  ```

- [ ] **5.5 Verificar logs**
  ```bash
  docker logs stack-scrapper --tail 100
  # Procurar por erros, warnings, timeouts
  ```

---

## Resumo Executivo

### Ordem de Dificuldade (mais fácil → mais difícil)

1. **Portais estáticos** (HTML puro + formulários simples)
2. **SPAs sem iframe** (TJSP)
3. **JSF/PrimeFaces** (PJE)
4. **SPAs com iframe** (TJRJ)
5. **Portais com captcha** (ainda não implementado)

### Tempo Estimado por Tribunal

| Complexidade | Tempo Implementação | Exemplo |
|--------------|---------------------|---------|
| Baixa | 4-6h | TJSP |
| Média | 6-8h | PJE |
| Alta | 8-12h | TJRJ |
| Muito Alta | 12-16h | Com captcha |

### Ferramentas Essenciais

```bash
# 1. Playwright Inspector (debug)
PWDEBUG=1 python your_script.py

# 2. Chrome DevTools
# Network tab - ver requisições
# Elements tab - inspecionar DOM
# Console tab - testar JavaScript

# 3. curl - testar endpoints
curl -X POST ... -d '{...}'

# 4. docker logs - ver erros
docker logs stack-scrapper --tail 100 -f
```

---

## Próximos Tribunais Sugeridos

### Fáceis (começar por aqui)
- TJCE - Similar ao TJSP
- TJSC - Similar ao TJSP
- TJPR - Similar ao TJSP

### Médios
- TJRS - Angular SPA, sem iframe
- TJMG - Sistema próprio
- TJBA - PJe similar

### Difíceis
- TRF2 - PJe com captcha
- TST - Sistema legado complexo
- STJ - Requer autenticação

---

## Contribuindo

Ao implementar um novo tribunal, por favor:

1. ✅ Documente peculiaridades no código
2. ✅ Adicione comentários sobre anti-bot
3. ✅ Salve screenshots de debug
4. ✅ Atualize este guia com learnings
5. ✅ Teste com múltiplos termos de busca

---

**Última atualização:** 2025-11-05
**Tribunais implementados:** TJSP, PJE/TRF1, TJRJ
**Próximo:** TJRJ consulta individual (detalhes do processo)
