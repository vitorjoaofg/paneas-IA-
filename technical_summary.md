# Como o LLM Sabe Quando/Como Chamar Tools - Resumo Técnico

## 🧠 Mecanismo Principal

O LLM usa **3 componentes principais** para decidir:

### 1. **Pattern Matching Semântico**
```python
# O modelo foi treinado para reconhecer padrões:
"consultar CPF" → tool_call
"oi/olá"       → resposta direta
"qual clima"   → tool_call (weather)
```

### 2. **Embeddings e Similaridade**
```python
# Cada input é convertido em vetor numérico
input_embedding = [0.9, 0.0, 0.8, 0.0, 0.1]  # "consultar CPF..."

# Compara com embeddings das tools disponíveis
tool_embeddings = {
    "unimed_consult": [0.8, 0.2, 0.9, 0.1, 0.7],  # Alta similaridade!
    "weather":        [0.1, 0.9, 0.2, 0.8, 0.3]   # Baixa similaridade
}

# Calcula score de similaridade cosseno
score(input, unimed_consult) = 0.85  # ✅ Usar esta tool
score(input, weather) = 0.16         # ❌ Não relevante
```

### 3. **Named Entity Recognition (NER)**
```python
# Extrai entidades do texto
"CPF 00835690490, nascido em 28/03/1979 em Natal"
↓
{
    "CPF": "00835690490",
    "DATA": "28/03/1979",
    "CIDADE": "Natal"
}
↓
# Mapeia para parâmetros da função
{
    "cpf": "00835690490",
    "data_nascimento": "1979-03-28",
    "cidade": "Natal_Tasy"
}
```

## 🔄 Fluxo de Decisão

```
Input: "Consultar CPF 00835690490..."
    ↓
[TOKENIZAÇÃO] → ['consultar', 'cpf', '00835690490', ...]
    ↓
[EMBEDDING] → [0.9, 0.0, 0.8, 0.0, 0.1]
    ↓
[SIMILARITY CHECK]
    • unimed_consult: 0.85 ✅
    • weather: 0.16
    • calculator: 0.28
    ↓
[DECISION: score > 0.5] → USE TOOL
    ↓
[EXTRACT ENTITIES] → {cpf, data_nascimento, cidade}
    ↓
[BUILD ARGUMENTS] → {"cpf": "00835690490", ...}
    ↓
[GENERATE JSON] → tool_call structure
```

## 🎯 Treinamento Específico

O modelo foi treinado com **milhões de exemplos** como:

```json
// Exemplo de treinamento 1
{
  "input": "oi",
  "output": {"content": "Olá! Como posso ajudar?"}
}

// Exemplo de treinamento 2
{
  "input": "consultar CPF 12345678901",
  "output": {
    "tool_calls": [{
      "function": {
        "name": "unimed_consult",
        "arguments": {"cpf": "12345678901", ...}
      }
    }]
  }
}
```

## 🔬 Por Dentro do Transformer

### Attention Mechanism
O modelo "presta atenção" em múltiplas partes simultaneamente:
- **Palavras-chave**: "consultar", "CPF", "contrato"
- **Descrição da tool**: "Consulta dados de beneficiário"
- **Contexto**: Relação entre palavras

### Multi-Head Attention
```python
# Cada "head" foca em aspectos diferentes:
head_1: Foco em entidades (CPF, datas)
head_2: Foco em ações (consultar, verificar)
head_3: Foco em contexto (Unimed, contratos)
head_4: Foco em localização (Natal, cidade)
```

## 📊 Decisão Final

```python
def should_use_tool(input_text, available_tools):
    # 1. Embedding do input
    input_emb = model.encode(input_text)

    # 2. Para cada tool disponível
    best_match = None
    best_score = 0.0

    for tool in available_tools:
        # 3. Calcula similaridade
        score = cosine_similarity(input_emb, tool.embedding)

        if score > best_score:
            best_score = score
            best_match = tool

    # 4. Threshold de decisão
    if best_score > 0.5:  # Threshold aprendido
        # 5. Extrai argumentos
        entities = extract_entities(input_text)
        arguments = map_to_parameters(entities, best_match)

        return {
            "tool_calls": [{
                "function": {
                    "name": best_match.name,
                    "arguments": arguments
                }
            }]
        }
    else:
        # Gera resposta direta
        return {"content": generate_response(input_text)}
```

## 🎓 Conceitos-Chave

1. **Fine-tuning**: Modelo ajustado especificamente para function calling
2. **Embeddings**: Representação vetorial do significado
3. **Threshold**: Valor limite para decisão (geralmente ~0.5)
4. **Slot Filling**: Preenchimento automático de parâmetros
5. **Tokens Especiais**: `<tool_call>`, `</tool_call>` no vocabulário

## ⚡ Performance

- **Latência**: ~100-500ms para decisão
- **Precisão**: ~95%+ em casos bem definidos
- **Embeddings**: Vetores de 4096+ dimensões
- **Contexto**: Até 128k tokens de janela

## 🔑 Resumo Final

O LLM decide usar tools através de:
1. **Análise semântica** do input
2. **Comparação de embeddings** com tools disponíveis
3. **Score de similaridade** > threshold
4. **Extração automática** de argumentos
5. **Geração estruturada** do JSON

Tudo isso acontece em **uma única forward pass** pela rede neural!