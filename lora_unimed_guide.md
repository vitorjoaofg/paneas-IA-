# 🎓 Guia Completo: LoRA para Atendente Unimed

## 📚 1. Conceito de LoRA

**LoRA (Low-Rank Adaptation)** adiciona matrizes de baixo rank (A e B) aos pesos do modelo:
```
W_novo = W_original + (A × B)
```

- **W_original**: Pesos congelados do modelo base (Qwen 32B)
- **A × B**: Adaptação treinável (muito menor que W)
- Tipicamente usa rank 8-64 (vs dimensão original de 4096+)

## 📊 2. Preparação do Dataset

### 2.1 Estrutura dos Dados de Treinamento

```jsonl
{"messages": [
    {"role": "system", "content": "Você é um atendente da Unimed Natal."},
    {"role": "user", "content": "oi"},
    {"role": "assistant", "content": "Olá! Bem-vindo ao atendimento Unimed Natal. Como posso ajudá-lo hoje?"}
]}

{"messages": [
    {"role": "user", "content": "preciso ver meu contrato"},
    {"role": "assistant", "content": "Para consultar seu contrato, vou precisar do seu CPF e data de nascimento. Pode me fornecer essas informações?"}
]}

{"messages": [
    {"role": "user", "content": "meu cpf é 12345678901"},
    {"role": "assistant", "content": "Obrigado pelo CPF. Agora preciso também da sua data de nascimento para prosseguir com a consulta."}
]}

{"messages": [
    {"role": "user", "content": "meu cpf é 12345678901 e nasci em 15/06/1985"},
    {"role": "assistant", "content": null, "tool_calls": [{"type": "function", "function": {"name": "unimed_consult", "arguments": "{\"cpf\": \"12345678901\", \"data_nascimento\": \"19850615\"}"}}]}
]}
```

### 2.2 Coletar Dados Reais

```python
import json
from typing import List, Dict

def prepare_training_data():
    """Prepara dataset para fine-tuning"""

    training_examples = []

    # 1. SAUDAÇÕES (100+ exemplos)
    saudacoes = [
        ("oi", "Olá! Bem-vindo ao atendimento Unimed Natal. Como posso ajudá-lo?"),
        ("bom dia", "Bom dia! É um prazer atendê-lo. Como posso auxiliar com seu plano Unimed?"),
        ("boa tarde", "Boa tarde! Sou do atendimento Unimed Natal. Em que posso ajudar?"),
        # ... mais variações
    ]

    # 2. CONSULTAS SEM DADOS (100+ exemplos)
    consultas_sem_dados = [
        ("quero ver meu contrato", "Para consultar seu contrato, preciso do seu CPF e data de nascimento."),
        ("preciso consultar meu plano", "Claro! Me forneça seu CPF e data de nascimento para acessar suas informações."),
        # ... mais variações
    ]

    # 3. DADOS PARCIAIS (200+ exemplos)
    dados_parciais = [
        ("meu cpf é 12345678901", "Obrigado pelo CPF. Agora preciso da sua data de nascimento."),
        ("nasci em 10/10/1990", "Obrigado pela data. Agora preciso do seu CPF para consultar."),
        # ... mais variações
    ]

    # 4. CONSULTAS COMPLETAS (500+ exemplos com tool calls)
    consultas_completas = [
        {
            "user": "cpf 12345678901, nascimento 15/06/1985",
            "tool_call": {
                "name": "unimed_consult",
                "args": {"cpf": "12345678901", "data_nascimento": "19850615"}
            }
        },
        # ... mais variações
    ]

    # 5. COMPORTAMENTO ESPECÍFICO UNIMED (200+ exemplos)
    especificos = [
        ("qual telefone da unimed natal?", "O telefone da Unimed Natal é (84) 4020-8900."),
        ("quais planos vocês têm?", "A Unimed Natal oferece diversos planos: Bronze, Prata, Ouro e Diamante..."),
        # ... informações específicas
    ]

    return training_examples

# Salvar como JSONL
with open('unimed_training.jsonl', 'w') as f:
    for example in prepare_training_data():
        f.write(json.dumps(example, ensure_ascii=False) + '\n')
```

## 🔧 3. Configuração do LoRA

### 3.1 Config para Qwen2.5 32B

```python
from peft import LoraConfig, get_peft_model, TaskType

lora_config = LoraConfig(
    r=32,  # Rank do LoRA (8-64 típico)
    lora_alpha=64,  # Scaling factor
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj"
    ],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
    inference_mode=False
)
```

### 3.2 Script de Treinamento

```python
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer
)
from peft import prepare_model_for_kbit_training
from datasets import load_dataset

# Carregar modelo base
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-32B-Instruct",
    load_in_4bit=True,  # Quantização para economizar memória
    device_map="auto",
    torch_dtype=torch.bfloat16
)

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-32B-Instruct")

# Preparar para LoRA
model = prepare_model_for_kbit_training(model)
model = get_peft_model(model, lora_config)

# Dataset
dataset = load_dataset("json", data_files="unimed_training.jsonl")

# Argumentos de treinamento
training_args = TrainingArguments(
    output_dir="./unimed-lora",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    warmup_ratio=0.03,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    evaluation_strategy="steps",
    eval_steps=100,
)

# Treinar
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    tokenizer=tokenizer,
)

trainer.train()

# Salvar LoRA
model.save_pretrained("unimed-lora-final")
```

## 🚀 4. Uso do LoRA Treinado

### 4.1 Carregar e Usar

```python
from peft import PeftModel

# Carregar modelo base
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-32B-Instruct",
    device_map="auto"
)

# Carregar LoRA
model = PeftModel.from_pretrained(
    base_model,
    "unimed-lora-final"
)

# Agora o modelo responde NATURALMENTE como atendente Unimed
# SEM PRECISAR de system prompt!

response = model.generate(
    "oi",  # Apenas a mensagem do usuário
    max_length=100
)
# Resposta: "Olá! Bem-vindo ao atendimento Unimed Natal..."
```

## 📈 5. Vantagens do LoRA

### ✅ **Prós:**
1. **Tamanho pequeno**: LoRA ~200MB vs modelo completo 65GB
2. **Treino rápido**: 3-6 horas com GPU decente
3. **Múltiplos LoRAs**: Pode ter vários (Unimed, Bradesco, etc)
4. **Sem system prompt**: Comportamento nativo
5. **Switching fácil**: Troca entre LoRAs em runtime

### ❌ **Contras:**
1. **Precisa dataset grande**: 5000+ exemplos de qualidade
2. **GPU necessária**: Mínimo 24GB VRAM para treinar
3. **Pode overfit**: Se dataset pequeno/repetitivo
4. **Manutenção**: Precisa retreinar quando mudam regras

## 💾 6. Estrutura Final

```
unimed-lora/
├── adapter_config.json      # Configuração do LoRA
├── adapter_model.safetensors # Pesos do LoRA (~200MB)
└── tokenizer/               # Tokenizer (se customizado)
```

## 🎯 7. Dataset Necessário

Para um LoRA de qualidade profissional:

- **10.000+ conversas** completas
- **500+ exemplos** de cada tipo de interação
- **1000+ tool calls** corretas
- **200+ edge cases** (erros, dados incorretos)
- **Dados reais** de atendimento (anonimizados)

## 🔬 8. Comando de Treinamento Completo

```bash
# Com Axolotl (recomendado)
accelerate launch -m axolotl.cli.train \
    --config unimed_lora_config.yml \
    --dataset_path ./unimed_training.jsonl \
    --output_dir ./unimed-lora \
    --num_epochs 3 \
    --batch_size 4 \
    --learning_rate 2e-4 \
    --lora_r 32 \
    --lora_alpha 64 \
    --gradient_checkpointing
```

## 💡 9. Exemplo de Config YAML (Axolotl)

```yaml
base_model: Qwen/Qwen2.5-32B-Instruct
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

load_in_4bit: true
adapter: lora
lora_r: 32
lora_alpha: 64
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj

datasets:
  - path: unimed_training.jsonl
    type: chat_template
    conversation: qwen

num_epochs: 3
micro_batch_size: 2
gradient_accumulation_steps: 8
learning_rate: 0.0002
warmup_ratio: 0.03

special_tokens:
  pad_token: "<|endoftext|>"
```

## ✨ 10. Resultado Final

Após treinar o LoRA:

```python
# SEM LoRA (modelo base):
User: "oi"
Assistant: "Hello! How can I help you?" # Genérico

# COM LoRA Unimed:
User: "oi"
Assistant: "Olá! Bem-vindo ao atendimento Unimed Natal. Como posso ajudá-lo com seu plano de saúde hoje?" # Específico!

# Comportamento aprendido nativamente:
User: "meu cpf é 12345678901"
Assistant: "Obrigado pelo seu CPF. Para acessar suas informações, também preciso da sua data de nascimento." # Sabe o fluxo!
```

O modelo "vira" um atendente Unimed NATIVO, sem precisar de instruções! 🎯