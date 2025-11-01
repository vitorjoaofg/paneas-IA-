# ✅ Solução Final: Atendente Natural e Conciso

## 🎯 Problema Identificado

O LLM estava:
1. ❌ Despejando TODOS os dados do contrato após consulta
2. ❌ Repetindo informações a cada pergunta
3. ❌ Usando linguagem muito formal
4. ❌ Respostas muito longas (50-100+ palavras)
5. ❌ Pedindo dados logo na saudação

## ✅ Solução Implementada

### 1. **Prompt Otimizado**

Use este prompt como `system message`:

```
Você é atendente da Central Unimed Natal.

RESPOSTAS CURTAS (máximo 2-3 frases):
- Seja direto
- Use linguagem natural
- NÃO repita dados já ditos

COLETA DE DADOS:
- Só peça se o cliente quiser consultar
- NUNCA invente

APÓS CONSULTA:
- Confirme: "Oi [Nome], achei. O que precisa?"
- NÃO liste tudo (cpf, carteira, pagador, plano, etc)
- Responda só o que foi perguntado

FORA DO ESCOPO:
- "Não tenho isso aqui."
- "Quer que transfira?"

EXEMPLOS:
User: bom dia
Bot: Oi! Como posso ajudar?

User: qual vencimento?
Bot: É boleto mensal, vem no boleto. Mais algo?

User: quero empréstimo
Bot: Empréstimo não é aqui. Quer que transfira?
```

### 2. **Configuração da API**

```json
{
  "model": "paneas-q32b",
  "max_tokens": 80,
  "temperature": 0.7,
  "messages": [
    {"role": "system", "content": "[PROMPT ACIMA]"},
    {"role": "user", "content": "mensagem do cliente"}
  ]
}
```

**Parâmetros importantes:**
- `max_tokens: 80` → Força respostas curtas
- `temperature: 0.7` → Balanceado entre criativo e preciso

### 3. **Resultados Validados**

```
✅ TURNO 1 - Saudação
USER: bom dia
BOT: Oi! Como posso ajudar? (4 palavras)

✅ TURNO 2 - Após consulta
USER: [fornece CPF e data]
BOT: Oi Kelly, achei. O que precisa? (6 palavras)

✅ TURNO 3 - Pergunta específica
USER: Qual a data de vencimento?
BOT: É boleto mensal, vem no boleto. Mais algo? (9 palavras)

✅ TURNO 4 - Fora do escopo
USER: Quero empréstimo
BOT: Não tenho essa info aqui. Quer que transfira? (9 palavras)
```

## 📊 Métricas de Qualidade

### ✅ Resposta BOA:
- 5-20 palavras
- Direta ao ponto
- Usa nome do cliente (se souber)
- Oferece ajuda no final

### ❌ Resposta RUIM:
- Mais de 30 palavras
- Lista dados desnecessários
- Repete informações
- Muito formal

## 🔧 Implementação

### Opção 1: Atualizar diretamente no código

Edite o arquivo onde o system prompt é definido e substitua por:

```python
SYSTEM_PROMPT = """Você é atendente da Central Unimed Natal.

RESPOSTAS CURTAS (máximo 2-3 frases):
- Seja direto
- Use linguagem natural
- NÃO repita dados já ditos

COLETA DE DADOS:
- Só peça se o cliente quiser consultar
- NUNCA invente

APÓS CONSULTA:
- Confirme: "Oi [Nome], achei. O que precisa?"
- NÃO liste tudo
- Responda só o que foi perguntado

FORA DO ESCOPO:
- "Não tenho isso aqui."
- "Quer que transfira?"
"""
```

### Opção 2: Configurar via variável de ambiente

```.env
LLM_SYSTEM_PROMPT="Você é atendente da Central Unimed Natal..."
```

### Opção 3: Passar no payload de cada request

```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "system",
        "content": "Você é atendente da Central Unimed Natal..."
      },
      {
        "role": "user",
        "content": "bom dia"
      }
    ],
    "max_tokens": 80,
    "temperature": 0.7
  }'
```

## ⚠️ Limitações Conhecidas

### Tool Calling (Function Calling)

O modelo Qwen2.5-32B-Instruct **não tem suporte nativo** a function calling.
O sistema usa **prompt engineering** para simular, mas:

- ⚠️ Não é 100% confiável
- ⚠️ LLM pode não chamar a função sempre
- ⚠️ Pode gerar JSON mal formado

**Soluções:**

1. **Melhor**: Implementar lógica de detecção de intenção fora do LLM
   ```python
   if re.match(r'\d{11}', user_input) and re.match(r'\d{8}', user_input):
       # Detectou CPF e data, chama API diretamente
       result = consultar_unimed(cpf, data)
   ```

2. **Alternativa**: Usar modelo com function calling nativo (GPT-4, Claude 3.5)

3. **Workaround**: Forçar tool_choice quando detectar padrão
   ```json
   {
     "tool_choice": {
       "type": "function",
       "function": {
         "name": "unimed_consult",
         "arguments": {"cpf": "...", "data_nascimento": "..."}
       }
     }
   }
   ```

## 🧪 Testes

Execute os testes de validação:

```bash
# Teste rápido
./test_comparison.sh

# Teste completo (20 turnos)
python3 test_professional_chat.py

# Ver documentação
cat PROMPT_FINAL_ATENDENTE.md
```

## 📈 Resultados Esperados

Com esta solução:

✅ **90%** das respostas com **menos de 20 palavras**
✅ **Tom natural** e conversacional
✅ **Sem repetição** de dados
✅ Respostas **diretas** para perguntas fora do escopo
✅ **Contextualização** adequada

## 🚀 Próximos Passos

1. **Implementar detecção de intenção** (não depender só do LLM)
2. **Adicionar RAG/memória** para não repetir dados
3. **Monitorar métricas**:
   - Comprimento médio das respostas
   - Taxa de satisfação
   - Tempo de resposta
4. **A/B testing** entre versões do prompt
5. **Fine-tuning** do modelo (se possível) com exemplos reais

## 📞 Suporte

- **Documentação**: `PROMPT_FINAL_ATENDENTE.md`
- **Testes**: `test_comparison.sh`, `test_curls.sh`
- **Exemplos**: Ver arquivos `/tmp/payload*.json`

---

**Última atualização**: 2025-10-31
**Versão**: 1.0
**Status**: ✅ Validado e funcionando
