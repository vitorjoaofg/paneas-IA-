#!/usr/bin/env python3
"""
Gerenciador de contexto para manter dados parciais entre turnos
Este módulo deve ser usado pelo backend para enriquecer as mensagens
"""

import re
from typing import Dict, Optional, List
import json

class ContextManager:
    """Gerencia contexto e dados parciais da conversa"""

    def __init__(self):
        self.collected_data = {}
        self.waiting_for = set()

    def extract_cpf(self, text: str) -> Optional[str]:
        """Extrai e limpa CPF"""
        clean = re.sub(r'[^\d]', '', text)
        matches = re.findall(r'\d{11}', clean)
        return matches[0] if matches else None

    def extract_date(self, text: str) -> Optional[str]:
        """Extrai e formata data de nascimento"""
        # DD/MM/AAAA ou DD-MM-AAAA
        pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})'
        match = re.search(pattern, text)
        if match:
            d, m, y = match.groups()
            return f"{y}{m.zfill(2)}{d.zfill(2)}"

        # Formato por extenso
        months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03',
            'abril': '04', 'maio': '05', 'junho': '06',
            'julho': '07', 'agosto': '08', 'setembro': '09',
            'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }
        for name, num in months.items():
            pattern = rf'(\d{{1,2}})\s+(?:de\s+)?{name}\s+(?:de\s+)?(\d{{4}})'
            match = re.search(pattern, text.lower())
            if match:
                d, y = match.groups()
                return f"{y}{num}{d.zfill(2)}"

        # Só ano-mês-dia
        pattern = r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'
        match = re.search(pattern, text)
        if match:
            y, m, d = match.groups()
            return f"{y}{m.zfill(2)}{d.zfill(2)}"

        return None

    def process_user_message(self, message: str) -> Dict:
        """Processa mensagem e extrai dados"""
        result = {
            "has_cpf": False,
            "has_date": False,
            "complete": False,
            "extracted": {}
        }

        # Extrai dados
        cpf = self.extract_cpf(message)
        date = self.extract_date(message)

        if cpf:
            self.collected_data['cpf'] = cpf
            result["has_cpf"] = True
            result["extracted"]["cpf"] = cpf

        if date:
            self.collected_data['data_nascimento'] = date
            result["has_date"] = True
            result["extracted"]["data_nascimento"] = date

        # Verifica se está completo
        result["complete"] = (
            'cpf' in self.collected_data and
            'data_nascimento' in self.collected_data
        )

        return result

    def get_missing_fields(self) -> List[str]:
        """Retorna lista de campos faltantes"""
        required = {'cpf', 'data_nascimento'}
        collected = set(self.collected_data.keys())
        return list(required - collected)

    def build_enhanced_message(self, original_message: str) -> str:
        """Constrói mensagem enriquecida com dados coletados"""
        if not self.collected_data:
            return original_message

        # Se tem dados completos, adiciona ao final da mensagem
        if 'cpf' in self.collected_data and 'data_nascimento' in self.collected_data:
            cpf = self.collected_data['cpf']
            date = self.collected_data['data_nascimento']
            # Formata data para exibição
            if len(date) == 8:
                formatted_date = f"{date[6:8]}/{date[4:6]}/{date[0:4]}"
            else:
                formatted_date = date

            return (
                f"{original_message}\n\n"
                f"[Contexto: Cliente já forneceu CPF {cpf} "
                f"e data de nascimento {formatted_date}]"
            )

        return original_message

    def should_use_tool(self, user_message: str) -> bool:
        """Decide se deve usar a ferramenta"""
        # Palavras que indicam intenção de consulta
        consultation_keywords = [
            'consultar', 'ver', 'verificar', 'checar',
            'contrato', 'plano', 'benefício', 'carteirinha',
            'mostrar', 'exibir', 'buscar', 'procurar'
        ]

        message_lower = user_message.lower()

        # Verifica se há intenção de consulta
        has_consultation_intent = any(
            keyword in message_lower
            for keyword in consultation_keywords
        )

        # Só usa tool se tem dados completos E intenção
        return (
            has_consultation_intent and
            'cpf' in self.collected_data and
            'data_nascimento' in self.collected_data
        )

    def get_context_prompt(self) -> str:
        """Retorna prompt de contexto para o sistema"""
        if not self.collected_data:
            return ""

        parts = []
        if 'cpf' in self.collected_data:
            cpf = self.collected_data['cpf']
            masked = f"{cpf[:3]}.***.***-{cpf[-2:]}"
            parts.append(f"CPF {masked}")

        if 'data_nascimento' in self.collected_data:
            parts.append("data de nascimento")

        if parts:
            collected = " e ".join(parts)
            missing = self.get_missing_fields()

            if missing:
                missing_text = " e ".join(missing)
                return f"\n[Contexto: Cliente já forneceu {collected}. Ainda falta: {missing_text}]"
            else:
                return f"\n[Contexto: Dados completos coletados - {collected}]"

        return ""

    def reset(self):
        """Limpa dados coletados"""
        self.collected_data.clear()
        self.waiting_for.clear()


# Exemplo de uso
if __name__ == "__main__":
    manager = ContextManager()

    test_messages = [
        "Oi, bom dia!",
        "Preciso consultar meu contrato",
        "Meu CPF é 123.456.789-01",
        "Nasci em 15 de junho de 1985",
        "Pode verificar agora?"
    ]

    print("="*60)
    print("TESTE DO GERENCIADOR DE CONTEXTO")
    print("="*60)

    for i, msg in enumerate(test_messages, 1):
        print(f"\nTurno {i}: \"{msg}\"")
        result = manager.process_user_message(msg)

        if result["extracted"]:
            print(f"  ✓ Dados extraídos: {result['extracted']}")

        if result["complete"]:
            print(f"  ✅ Dados completos!")
        else:
            missing = manager.get_missing_fields()
            if missing:
                print(f"  ⚠️  Faltando: {', '.join(missing)}")

        should_tool = manager.should_use_tool(msg)
        print(f"  🔧 Usar ferramenta? {'SIM' if should_tool else 'NÃO'}")

        context = manager.get_context_prompt()
        if context:
            print(f"  📝 Contexto: {context}")

    print("\n" + "="*60)
    print("Dados finais coletados:", manager.collected_data)