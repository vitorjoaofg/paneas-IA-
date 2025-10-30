#!/usr/bin/env python3
"""
Script Completo de Treinamento LoRA para UNIMED NATAL
Com progresso visual e monitoramento em tempo real
Dataset: 100.000+ conversas realistas de atendimento
"""

import os
import json
import torch
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import gc
import inspect
import warnings

import torch.nn as nn

# Configurações de ambiente - DEVE vir ANTES de qualquer import de ML
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['WANDB_MODE'] = 'disabled'  # Desabilita wandb para evitar erros
os.environ['HF_HUB_OFFLINE'] = '1'  # Modo offline para Hugging Face

def get_env_int(key: str, default: int) -> int:
    """Lê um inteiro das variáveis de ambiente com fallback seguro."""
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def get_rank() -> int:
    """Rank global do processo (0 = primário)."""
    return get_env_int("RANK", 0)


def get_world_size() -> int:
    """Quantidade total de processos distribuídos."""
    return get_env_int("WORLD_SIZE", 1)


def get_local_rank() -> int:
    """Rank local dentro do nó."""
    return get_env_int("LOCAL_RANK", 0)


def is_main_process() -> bool:
    """Indica se este é o processo primário."""
    return get_rank() == 0


def is_awq_quantized(model) -> bool:
    """Detecta se o modelo está com quantização AWQ."""
    quantization_method = getattr(model, "quantization_method", None)
    if isinstance(quantization_method, str) and "awq" in quantization_method.lower():
        return True

    quant_config = getattr(model, "quantization_config", None)
    if quant_config is not None:
        # Alguns loaders expõem quant_method, outros method ou config_name
        for attr in ("quant_method", "method", "config_name", "name"):
            value = getattr(quant_config, attr, None)
            if isinstance(value, str) and "awq" in value.lower():
                return True

    return False


if is_main_process():
    print("=" * 80)
    print("🚀 TREINAMENTO LoRA - UNIMED NATAL")
    print("=" * 80)
    print(f"🏥 Cliente: UNIMED NATAL")
    print(f"📊 Dataset: 100.000+ conversas realistas de atendimento médico")
    print(f"🎯 Objetivo: Atendente virtual especializado Unimed")
    print(f"⏰ Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if torch.cuda.is_available():
        print(f"🖥️  GPUs disponíveis: {torch.cuda.device_count()} | world_size={get_world_size()}")
    else:
        print("🖥️  Nenhuma GPU detectada - rodando em CPU")
    print(f"🔧 Técnica: LoRA (Low-Rank Adaptation)")
    print(f"📦 Modelo base: Qwen2.5-32B-Instruct (4-bit)")
    print("=" * 80)

# Importações após configurar CUDA
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType
)
from datasets import Dataset
from tqdm import tqdm

class UnimedDataset:
    """Dataset loader com progresso"""

    def __init__(self, file_path: str, tokenizer, max_length: int = 2048):
        self.file_path = file_path
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.conversations = []

    def load(self, max_samples: int = None):
        """Carrega dataset com barra de progresso"""
        if is_main_process():
            print("\n📂 Carregando dataset Unimed...")

        # Primeiro, gera o dataset se não existir
        if not Path(self.file_path).exists():
            if is_main_process():
                print("  ⚠️  Dataset não encontrado. Gerando 100.000 conversas realistas...")
                print("  ⏳ Isso pode levar alguns minutos...")
                os.system("python3 generate_100k_realistic_dataset.py")
            else:
                # Aguarda o dataset ser gerado pelo processo principal
                while not Path(self.file_path).exists():
                    time.sleep(5)

        # Carrega conversas
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total = min(len(lines), max_samples) if max_samples else len(lines)

            for i, line in enumerate(
                tqdm(
                    lines[:total],
                    desc="  Carregando conversas",
                    disable=not is_main_process()
                )
            ):
                conv = json.loads(line)
                self.conversations.append(conv)

        if is_main_process():
            print(f"  ✅ {len(self.conversations):,} conversas carregadas")

        # Estatísticas do dataset
        with_tools = sum(1 for c in self.conversations
                        if any(m.get('tool_calls') for m in c['messages'] if m.get('role') == 'assistant'))
        if is_main_process():
            print(f"  📊 Com tool calls: {with_tools:,} ({with_tools/len(self.conversations)*100:.1f}%)")

        return self

    def prepare_for_training(self):
        """Prepara dataset para treinamento"""
        if is_main_process():
            print("\n🔧 Preparando dados para treinamento...")

        training_data = []

        for conv in tqdm(
            self.conversations,
            desc="  Tokenizando",
            disable=not is_main_process()
        ):
            # Formata conversa para o modelo
            text = self.format_conversation(conv['messages'])

            # Tokeniza com padding e truncation adequados
            tokens = self.tokenizer(
                text,
                truncation=True,
                max_length=self.max_length,
                padding="max_length",  # Adiciona padding até max_length
                return_tensors=None    # Retorna listas, não tensors
            )

            # Cria labels copiando input_ids
            tokens['labels'] = tokens['input_ids'].copy()

            # Marca tokens de padding como -100 para serem ignorados no loss
            tokens['labels'] = [
                -100 if token_id == self.tokenizer.pad_token_id else token_id
                for token_id in tokens['labels']
            ]

            training_data.append(tokens)

        return Dataset.from_list(training_data)

    def format_conversation(self, messages: List[Dict]) -> str:
        """Formata conversa no formato Qwen"""
        formatted = ""

        for msg in messages:
            role = msg['role']
            content = msg.get('content', '')

            if role == 'user':
                formatted += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == 'assistant':
                if msg.get('tool_calls'):
                    # Formata tool call
                    tool_call = msg['tool_calls'][0]
                    formatted += f"<|im_start|>assistant\n"
                    formatted += f"<tool_call>\n"
                    formatted += f"{json.dumps(tool_call)}\n"
                    formatted += f"</tool_call><|im_end|>\n"
                else:
                    formatted += f"<|im_start|>assistant\n{content}<|im_end|>\n"
            elif role == 'system':
                formatted += f"<|im_start|>system\n{content}<|im_end|>\n"

        return formatted

def prepare_awq_model_for_training(
    model,
    use_gradient_checkpointing: bool = True,
    gradient_checkpointing_kwargs: Dict | None = None,
) -> torch.nn.Module:
    """Versão adaptada de prepare_model_for_kbit_training que não converte AWQ para fp32."""
    if gradient_checkpointing_kwargs is None:
        gradient_checkpointing_kwargs = {}

    loaded_in_kbit = getattr(model, "is_loaded_in_8bit", False) or getattr(model, "is_loaded_in_4bit", False)
    quant_method_attr = getattr(model, "quantization_method", None)
    is_gptq_quantized = quant_method_attr == "gptq"
    is_aqlm_quantized = quant_method_attr == "aqlm"
    is_eetq_quantized = quant_method_attr == "eetq"
    is_torchao_quantized = quant_method_attr == "torchao"
    is_hqq_quantized = quant_method_attr == "hqq" or getattr(model, "hqq_quantized", False)
    is_awq = is_awq_quantized(model)

    # 1) Congela pesos originais
    for _, param in model.named_parameters():
        param.requires_grad = False

    # 2) Upcast controlado
    if (
        not is_gptq_quantized
        and not is_aqlm_quantized
        and not is_eetq_quantized
        and not is_hqq_quantized
        and not is_torchao_quantized
        and not is_awq
    ):
        for param in model.parameters():
            if (param.dtype == torch.float16 or param.dtype == torch.bfloat16) and param.__class__.__name__ != "Params4bit":
                param.data = param.data.to(torch.float32)
    elif is_awq:
        # Para AWQ somente LayerNorm em fp32 para estabilidade.
        for module in model.modules():
            if isinstance(module, nn.LayerNorm):
                module.to(torch.float32)

    if getattr(model, "config", None) is not None:
        model.config.use_cache = False

    # 3) Gradient checkpointing e enable grads nos inputs
    if (
        use_gradient_checkpointing
        and (
            loaded_in_kbit
            or is_gptq_quantized
            or is_aqlm_quantized
            or is_eetq_quantized
            or is_hqq_quantized
            or is_torchao_quantized
            or is_awq
        )
    ):
        if "use_reentrant" not in gradient_checkpointing_kwargs or gradient_checkpointing_kwargs["use_reentrant"]:
            if hasattr(model, "enable_input_require_grads"):
                model.enable_input_require_grads()
            else:

                def make_inputs_require_grad(module, input, output):
                    output.requires_grad_(True)

                model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)

        supports_kwargs = "gradient_checkpointing_kwargs" in list(
            inspect.signature(model.gradient_checkpointing_enable).parameters
        )
        if not supports_kwargs and gradient_checkpointing_kwargs:
            warnings.warn(
                "gradient_checkpointing_kwargs não suportado nesta versão do Transformers; argumentos ignorados.",
                FutureWarning,
            )
            gradient_checkpointing_kwargs = {}

        gc_kwargs = (
            {}
            if not supports_kwargs
            else {"gradient_checkpointing_kwargs": gradient_checkpointing_kwargs}
        )
        model.gradient_checkpointing_enable(**gc_kwargs)

    return model

def setup_model_and_tokenizer(local_rank: int):
    """Configura modelo e tokenizer com quantização"""
    if is_main_process():
        print("\n🤖 Configurando modelo e tokenizer...")

    model_path = "/srv/models/qwen2_5/int4-awq-32b"

    if is_main_process():
        print("  📥 Carregando tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="left"
    )

    # Adiciona tokens especiais se necessário
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if is_main_process():
        print("  📥 Carregando modelo Qwen 32B AWQ (já quantizado)...")
        print("  ⏳ Isso pode levar 2-3 minutos...")

    # Como o modelo já está em AWQ, carregamos diretamente sem BitsAndBytes
    device_map = {"": local_rank} if torch.cuda.is_available() else None
    try:
        # Primeiro tenta carregar com AWQ config nativo
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch.float16  # AWQ usa float16
        )
    except Exception as e:
        if is_main_process():
            print(f"  ⚠️  Falha ao carregar AWQ nativo: {e}")
            print("  🔄 Tentando com quantização BitsAndBytes...")

        # Fallback para BitsAndBytes se AWQ falhar
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch.float16
        )

    if is_main_process():
        print("  ✅ Modelo carregado com sucesso!")

    # Prepara modelo para treinamento
    model = prepare_awq_model_for_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    return model, tokenizer

def setup_lora(model):
    """Configura LoRA"""
    if is_main_process():
        print("\n⚙️  Configurando LoRA para Unimed...")

    lora_config = LoraConfig(
        r=32,  # Rank (pode ajustar: 8, 16, 32, 64)
        lora_alpha=64,  # Alpha (geralmente 2x o rank)
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

    model = get_peft_model(model, lora_config)

    # Estatísticas
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())

    if is_main_process():
        print(f"  📊 Parâmetros treináveis: {trainable_params:,} ({trainable_params/total_params*100:.2f}%)")
        print(f"  📊 Total de parâmetros: {total_params:,}")
        print(f"  💾 Tamanho estimado do LoRA: ~{trainable_params * 2 / 1024 / 1024:.0f}MB")

    return model

def train_model(model, tokenizer, train_dataset):
    """Treina o modelo com progresso visual"""
    if is_main_process():
        print("\n🎯 Iniciando treinamento LoRA Unimed...")

    # Argumentos de treinamento otimizados para GPUs disponíveis
    training_args = TrainingArguments(
        output_dir="./unimed-lora-checkpoints",
        num_train_epochs=3,  # 3 épocas
        per_device_train_batch_size=2,  # Batch size pequeno para caber na memória
        gradient_accumulation_steps=8,  # Acumula gradientes
        warmup_steps=100,
        learning_rate=2e-4,
        fp16=True,  # Mixed precision
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        eval_strategy="no",  # Sem validação por enquanto (nome correto do parâmetro)
        load_best_model_at_end=False,
        report_to="none",  # Desabilita wandb/tensorboard
        gradient_checkpointing=True,  # Economiza memória
        optim="paged_adamw_8bit",  # Otimizador eficiente
        logging_dir="./logs",
        remove_unused_columns=False,
        group_by_length=True,  # Agrupa sequências similares
        dataloader_num_workers=4,
        ddp_find_unused_parameters=False,
        # Callbacks para mostrar progresso
        disable_tqdm=not is_main_process(),  # Barra apenas no processo principal
    )

    # Data collator - sem padding adicional pois já fizemos no dataset
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
        pad_to_multiple_of=None  # Já fizemos padding no dataset
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
        tokenizer=tokenizer
    )

    # Callback personalizado para mostrar métricas
    from transformers import TrainerCallback

    class ProgressCallback(TrainerCallback):
        def __init__(self):
            super().__init__()
            self.start_time = time.time()
            self.last_loss = None

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not is_main_process():
                return
            if logs:
                if 'loss' in logs:
                    self.last_loss = logs['loss']
                    elapsed = time.time() - self.start_time
                    print(f"\n  📈 Step {state.global_step} | Loss: {logs['loss']:.4f} | Tempo: {elapsed/60:.1f}min")

    trainer.add_callback(ProgressCallback())

    if is_main_process():
        print("\n" + "="*60)
        print("🏃 TREINAMENTO UNIMED EM ANDAMENTO")
        print("="*60)
        print("Configuração:")
        print(f"  • Cliente: Unimed Natal")
        print(f"  • Épocas: {training_args.num_train_epochs}")
        print(f"  • Batch size efetivo: {training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps}")
        print(f"  • Learning rate: {training_args.learning_rate}")
        print(f"  • Warmup steps: {training_args.warmup_steps}")
        print("\n⏳ Tempo estimado: 3-6 horas")
        print("\n💡 Você verá atualizações a cada 10 steps")
        print("="*60 + "\n")

    # Treina!
    trainer.train()

    return trainer

def save_final_model(model, tokenizer):
    """Salva modelo final"""
    print("\n💾 Salvando modelo Unimed treinado...")

    output_dir = "./unimed-lora-final"
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Cria diretório de produção
    prod_dir = "/srv/models/loras/unimed"

    print(f"  ✅ Modelo salvo em: {output_dir}")
    print(f"\n📦 Para mover para produção, execute:")
    print(f"  sudo mkdir -p {prod_dir}")
    print(f"  sudo cp -r {output_dir}/* {prod_dir}/")
    print(f"  sudo chown -R root:root {prod_dir}")

    return output_dir

def test_model(model, tokenizer):
    """Testa o modelo treinado"""
    print("\n🧪 Testando modelo Unimed treinado...")

    test_cases = [
        "oi",
        "bom dia",
        "preciso ver meu contrato",
        "meu cpf é 12345678901 e nasci em 15/06/1985"
    ]

    model.eval()

    for test_input in test_cases:
        print(f"\n  👤 Cliente: '{test_input}'")

        inputs = tokenizer(
            f"<|im_start|>user\n{test_input}<|im_end|>\n<|im_start|>assistant\n",
            return_tensors="pt"
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Extrai apenas a resposta do assistente
        if "assistant" in response:
            response = response.split("assistant")[-1].strip()
        print(f"  🤖 Unimed: '{response[:150]}...'")

def main():
    """Pipeline completo de treinamento"""

    try:
        local_rank = get_local_rank()
        if torch.cuda.is_available():
            torch.cuda.set_device(local_rank)

        # 1. Configura modelo e tokenizer
        model, tokenizer = setup_model_and_tokenizer(local_rank)

        # 2. Configura LoRA
        model = setup_lora(model)

        # 3. Carrega e prepara dataset
        dataset = UnimedDataset("unimed_dataset_100k.jsonl", tokenizer)
        dataset.load(max_samples=100000)  # Usa 100k conversas completas
        train_data = dataset.prepare_for_training()

        # 4. Treina
        trainer = train_model(model, tokenizer, train_data)

        if trainer.is_world_process_zero():
            # 5. Salva modelo final
            output_dir = save_final_model(trainer.model, tokenizer)

            # 6. Testa
            test_model(trainer.model, tokenizer)

            print("\n" + "="*80)
            print("✅ TREINAMENTO UNIMED NATAL CONCLUÍDO COM SUCESSO!")
            print("="*80)
            print(f"⏰ Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📁 Modelo LoRA salvo em: {output_dir}")
            print(f"🏥 Cliente: UNIMED NATAL")
            print(f"📊 Dataset: 100.000 conversas médicas treinadas")
            print(f"🎯 Modelo: Atendente virtual especializado Unimed")
            print("\n🚀 Próximos passos:")
            print("  1. Teste o modelo com casos reais de atendimento")
            print("  2. Mova para produção: /srv/models/loras/unimed")
            print("  3. Configure vLLM para usar o LoRA da Unimed")
            print("  4. Reinicie os serviços ASR que foram pausados:")
            print("     docker start stack-asr-gpu0 stack-asr-gpu1")
            print("\n💡 Dica: O modelo agora responde nativamente como Unimed!")
            print("="*80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Treinamento interrompido pelo usuário")
        print("📌 Para continuar de onde parou, use o checkpoint mais recente")
    except Exception as e:
        print(f"\n❌ Erro durante treinamento: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpa memória
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        if is_main_process():
            print("\n🧹 Memória GPU liberada")

if __name__ == "__main__":
    main()
