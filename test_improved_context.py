#!/usr/bin/env python3
"""
Teste melhorado com gestão de contexto e memória de dados parciais
"""

import json
import requests
import re
from typing import Dict, List, Optional, Tuple

API_URL = "https://jota.ngrok.app/api/v1/chat/completions"
AUTH_TOKEN = "token_abc123"

class ImprovedChatHandler:
    """Gerenciador melhorado com memória de contexto"""

    def __init__(self):
        self.conversation_history = []
        self.partial_data = {}  # Armazena CPF e data temporariamente
        self.max_history = 10  # Limita histórico para evitar confusão

    def extract_cpf(self, text: str) -> Optional[str]:
        """Extrai CPF do texto"""
        # Remove pontuação
        clean_text = re.sub(r'[.-]', '', text)
        # Busca padrão de 11 dígitos
        cpf_match = re.search(r'\b\d{11}\b', clean_text)
        if cpf_match:
            return cpf_match.group()
        return None

    def extract_date(self, text: str) -> Optional[str]:
        """Extrai data de nascimento do texto"""
        # Formato DD/MM/AAAA
        date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if date_match:
            day, month, year = date_match.groups()
            return f"{year}{month.zfill(2)}{day.zfill(2)}"

        # Formato verbal "15 de junho de 1985"
        months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }
        for month_name, month_num in months.items():
            pattern = rf'(\d{{1,2}})\s+de\s+{month_name}\s+de\s+(\d{{4}})'
            match = re.search(pattern, text.lower())
            if match:
                day, year = match.groups()
                return f"{year}{month_num}{day.zfill(2)}"

        return None

    def update_partial_data(self, user_message: str):
        """Atualiza dados parciais com informações da mensagem"""
        cpf = self.extract_cpf(user_message)
        date = self.extract_date(user_message)

        if cpf:
            self.partial_data['cpf'] = cpf
            print(f"   📌 CPF detectado: {cpf}")

        if date:
            self.partial_data['data_nascimento'] = date
            print(f"   📌 Data detectada: {date}")

        return bool(cpf or date)

    def has_complete_data(self) -> bool:
        """Verifica se tem todos os dados necessários"""
        return 'cpf' in self.partial_data and 'data_nascimento' in self.partial_data

    def get_enhanced_system_prompt(self) -> str:
        """Retorna system prompt com contexto de dados parciais"""
        base_prompt = """Você é um atendente da Central de Atendimento Unimed Natal.

REGRAS IMPORTANTES:
- Seja sempre cordial e profissional
- Para consultar contratos, você precisa do CPF e data de nascimento
- NUNCA mencione termos técnicos ou nomes de sistemas
"""

        # Adiciona contexto de dados parciais se existirem
        if self.partial_data:
            if 'cpf' in self.partial_data and 'data_nascimento' not in self.partial_data:
                base_prompt += f"\n\nCONTEXTO: O cliente já forneceu o CPF: {self.partial_data['cpf'][:3]}***.***-**. Ainda preciso da data de nascimento."
            elif 'data_nascimento' in self.partial_data and 'cpf' not in self.partial_data:
                base_prompt += f"\n\nCONTEXTO: O cliente já forneceu a data de nascimento. Ainda preciso do CPF."
            elif self.has_complete_data():
                base_prompt += f"\n\nCONTEXTO: Já tenho os dados necessários para consulta (CPF e data de nascimento)."

        base_prompt += """

COMO RESPONDER:
- Se faltar apenas um dado, peça especificamente o que falta
- Se tiver todos os dados, proceda com a consulta
- Sempre confirme quando receber informações importantes"""

        return base_prompt

    def manage_history(self):
        """Gerencia o histórico para evitar contexto muito longo"""
        if len(self.conversation_history) > self.max_history:
            # Mantém apenas as mensagens mais recentes
            self.conversation_history = self.conversation_history[-self.max_history:]

            # Adiciona um resumo se necessário
            if len(self.conversation_history) > 6:
                summary = {
                    "role": "system",
                    "content": "Resumo: Cliente em atendimento sobre contratos Unimed."
                }
                self.conversation_history = [summary] + self.conversation_history[-6:]

    def process_message(self, user_message: str, test_name: str) -> Tuple[bool, str]:
        """Processa uma mensagem do usuário"""
        print(f"\n{'='*60}")
        print(f"📝 {test_name}")
        print(f"{'='*60}")
        print(f"👤 Cliente: {user_message}")

        # Atualiza dados parciais
        self.update_partial_data(user_message)

        # Adiciona mensagem do usuário ao histórico
        self.conversation_history.append({"role": "user", "content": user_message})

        # Gerencia tamanho do histórico
        self.manage_history()

        # Prepara payload
        messages = [
            {"role": "system", "content": self.get_enhanced_system_prompt()},
            *self.conversation_history
        ]

        payload = {
            "model": "paneas-q32b",
            "messages": messages,
            "max_tokens": 256,
            "temperature": 0.7,
            "tools": [{
                "type": "function",
                "function": {
                    "name": "unimed_consult",
                    "description": "Consulta dados do beneficiário",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_url": {"type": "string", "default": "https://unimed-central-cobranca.paneas.net/api/v1"},
                            "cidade": {"type": "string", "default": "Natal_Tasy"},
                            "tipo": {"type": "string", "default": "Contratos"},
                            "protocolo": {"type": "string", "default": "0"},
                            "cpf": {"type": "string"},
                            "data_nascimento": {"type": "string"}
                        },
                        "required": ["cpf", "data_nascimento"]
                    }
                }
            }],
            "tool_choice": "auto"
        }

        # Se tem dados completos, pode forçar uso da tool
        if self.has_complete_data() and "consult" in user_message.lower():
            # Injeta os dados coletados no contexto
            payload["messages"][-1]["content"] += f"\n[Dados coletados: CPF {self.partial_data['cpf']}, nascimento {self.partial_data['data_nascimento']}]"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}"
        }

        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            result = response.json()

            if "choices" in result:
                message = result["choices"][0]["message"]
                content = message.get("content")
                tool_calls = message.get("tool_calls")

                if tool_calls:
                    print("✅ AÇÃO: Consultando sistema com dados completos")
                    # Limpa dados parciais após uso
                    self.partial_data.clear()
                    # Adiciona resposta ao histórico
                    self.conversation_history.append(message)
                    return True, "Tool executada com sucesso"
                elif content:
                    print(f"🤖 Atendente: {content}")
                    # Adiciona resposta ao histórico
                    self.conversation_history.append({"role": "assistant", "content": content})
                    return True, content

            return False, "Erro na resposta"

        except Exception as e:
            return False, f"Erro: {str(e)}"

def run_advanced_tests():
    """Executa testes com dados em turnos separados"""
    print("="*80)
    print("🔬 TESTE AVANÇADO - DADOS EM TURNOS SEPARADOS")
    print("="*80)

    handler = ImprovedChatHandler()

    # Cenário 1: CPF primeiro, depois data
    test_cases = [
        ("oi, bom dia", "Saudação"),
        ("preciso consultar meu contrato", "Pedido sem dados"),
        ("meu cpf é 12345678901", "Fornece apenas CPF"),
        ("nasci em 15/06/1985", "Fornece data (completa dados)"),
        ("pode consultar agora?", "Confirmação com dados completos"),
    ]

    print("\n🔹 CENÁRIO 1: Dados fornecidos em turnos separados")
    for message, description in test_cases:
        handler.process_message(message, description)

    # Cenário 2: Nova conversa com contexto limpo
    handler2 = ImprovedChatHandler()

    print("\n\n🔹 CENÁRIO 2: Data primeiro, depois CPF")
    test_cases2 = [
        ("olá", "Saudação"),
        ("nasci em 20/12/2000", "Fornece data primeiro"),
        ("preciso ver meus contratos", "Pedido de consulta"),
        ("meu cpf é 98765432100", "Fornece CPF (completa dados)"),
    ]

    for message, description in test_cases2:
        handler2.process_message(message, description)

    print("\n" + "="*80)
    print("💡 MELHORIAS IMPLEMENTADAS")
    print("="*80)
    print("""
    ✅ Memória de dados parciais (CPF e data em turnos separados)
    ✅ Gestão de histórico (máximo 10 mensagens)
    ✅ Contexto dinâmico no system prompt
    ✅ Extração inteligente de dados em diferentes formatos
    ✅ Limpeza de dados após uso
    """)

if __name__ == "__main__":
    run_advanced_tests()