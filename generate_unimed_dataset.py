#!/usr/bin/env python3
"""
Gerador de Dataset Sintético para LoRA Unimed
Gera 10.000+ conversas realistas de atendimento
"""

import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import itertools

class UnimedDatasetGenerator:
    """Gerador de conversas sintéticas para treinamento"""

    def __init__(self):
        # Dados realistas brasileiros
        self.nomes = [
            "João Silva", "Maria Santos", "José Oliveira", "Ana Costa",
            "Pedro Souza", "Juliana Lima", "Carlos Ferreira", "Patricia Alves",
            "Lucas Pereira", "Fernanda Rodrigues", "Rafael Gomes", "Camila Martins",
            "Bruno Ribeiro", "Amanda Carvalho", "Marcos Almeida", "Beatriz Dias"
        ]

        self.cidades = ["Natal", "Parnamirim", "Mossoró", "São Gonçalo do Amarante"]

        # Variações de saudações
        self.saudacoes = [
            "oi", "olá", "bom dia", "boa tarde", "boa noite",
            "oi, tudo bem?", "olá, boa tarde", "oi, bom dia",
            "alô", "alo", "ei", "opa", "e aí",
            "bom dia, tudo bem?", "boa tarde, como vai?"
        ]

        # Variações de pedidos de consulta
        self.pedidos_consulta = [
            "preciso ver meu contrato",
            "quero consultar meu plano",
            "pode verificar meus dados?",
            "gostaria de ver meu contrato",
            "preciso consultar minha carteirinha",
            "quero ver meus benefícios",
            "pode checar meu plano?",
            "preciso verificar meu contrato",
            "queria consultar meus dados",
            "me mostra meu contrato",
            "consulta meu plano aí",
            "verifica meu contrato por favor",
            "preciso de informações do meu plano"
        ]

        # Formas de fornecer CPF
        self.formas_cpf = [
            "meu cpf é {cpf}",
            "cpf {cpf}",
            "{cpf}",
            "o cpf é {cpf}",
            "CPF: {cpf}",
            "segue meu cpf: {cpf}",
            "meu cpf {cpf}",
            "é {cpf}",
            "cpf é o {cpf}",
            "anota aí: {cpf}"
        ]

        # Formas de fornecer data
        self.formas_data = [
            "nasci em {data}",
            "data de nascimento {data}",
            "{data}",
            "nascimento: {data}",
            "nasci dia {data}",
            "minha data de nascimento é {data}",
            "data nascimento {data}",
            "nascido em {data}",
            "{data} é minha data de nascimento"
        ]

        # Perguntas frequentes
        self.perguntas_frequentes = [
            ("qual o telefone da unimed?", "O telefone da Unimed Natal é (84) 4020-8900. Atendimento de segunda a sexta, das 8h às 18h."),
            ("qual horário de atendimento?", "Nosso atendimento telefônico funciona de segunda a sexta, das 8h às 18h. O atendimento online está disponível 24 horas."),
            ("quais planos vocês tem?", "A Unimed Natal oferece os planos: Bronze, Prata, Ouro e Diamante, com diferentes coberturas e valores."),
            ("como faço para incluir dependente?", "Para incluir dependente, você precisa apresentar documentos no balcão de atendimento: RG, CPF, certidão de nascimento ou casamento e comprovante de residência."),
            ("onde fica a unimed?", "Nossa sede fica na Av. Nascimento de Castro, 1660 - Lagoa Nova, Natal/RN. Temos também unidades em Parnamirim e Mossoró."),
            ("vocês atendem emergência?", "Sim, temos atendimento 24h de urgência e emergência em nossa rede credenciada. Consulte os hospitais credenciados em seu plano."),
            ("como marcar consulta?", "Você pode marcar consultas através do app Unimed Natal, pelo site ou telefone (84) 4020-8900."),
            ("qual a carência?", "O período de carência varia: consultas 30 dias, exames simples 60 dias, exames complexos 180 dias, partos 300 dias."),
            ("pode parcelar?", "Sim, oferecemos parcelamento em até 12x no cartão de crédito para pagamentos anuais."),
            ("tem desconto?", "Oferecemos descontos para pagamento anual à vista e planos empresariais. Consulte condições.")
        ]

        # Respostas do assistente
        self.respostas_saudacao = [
            "Olá! Bem-vindo ao atendimento Unimed Natal. Como posso ajudá-lo hoje?",
            "Oi! Sou do atendimento Unimed Natal. Em que posso ajudar?",
            "Bom dia! É um prazer atendê-lo. Como posso auxiliar com seu plano Unimed?",
            "Boa tarde! Unimed Natal, como posso ser útil?",
            "Olá! Como posso ajudá-lo com seu plano de saúde hoje?",
            "Oi! Seja bem-vindo à Unimed Natal. Como posso auxiliar?"
        ]

        self.respostas_pedir_dados = [
            "Para consultar seus dados, vou precisar do seu CPF e data de nascimento. Pode me informar?",
            "Claro! Para acessar seu contrato, preciso do CPF e data de nascimento. Por favor, forneça essas informações.",
            "Posso verificar sim! Me informe seu CPF e data de nascimento para consultar.",
            "Para prosseguir com a consulta, preciso que me forneça seu CPF e data de nascimento.",
            "Vou consultar seus dados. Por favor, me informe CPF e data de nascimento.",
            "Certo! Preciso do seu CPF e data de nascimento para acessar suas informações."
        ]

        self.respostas_pedir_data = [
            "Obrigado pelo CPF. Agora preciso também da sua data de nascimento para continuar.",
            "Recebi o CPF. Pode me informar sua data de nascimento?",
            "Perfeito! Agora só falta a data de nascimento para completar a consulta.",
            "CPF anotado! Qual sua data de nascimento?",
            "Ok, já tenho o CPF. Me informe também quando você nasceu.",
            "Certo! Para continuar, preciso da sua data de nascimento."
        ]

        self.respostas_pedir_cpf = [
            "Obrigado pela data. Agora preciso do seu CPF para consultar.",
            "Data anotada! Pode me informar seu CPF?",
            "Perfeito! Agora só preciso do número do seu CPF.",
            "Ok, já anotei a data. Qual seu CPF?",
            "Recebi a data de nascimento. Me informe também seu CPF.",
            "Certo! Para prosseguir, preciso do número do seu CPF."
        ]

    def gerar_cpf(self) -> str:
        """Gera CPF válido aleatório"""
        def calculate_digit(cpf_digits):
            sum_digits = sum((10 - i) * int(digit) for i, digit in enumerate(cpf_digits))
            remainder = sum_digits % 11
            return '0' if remainder < 2 else str(11 - remainder)

        base = [random.randint(0, 9) for _ in range(9)]
        base_str = ''.join(map(str, base))

        first_digit = calculate_digit(base_str)
        second_digit = calculate_digit(base_str + first_digit)

        return base_str + first_digit + second_digit

    def gerar_data_nascimento(self) -> tuple:
        """Gera data de nascimento aleatória"""
        start_date = datetime(1950, 1, 1)
        end_date = datetime(2005, 12, 31)

        random_date = start_date + timedelta(
            days=random.randint(0, (end_date - start_date).days)
        )

        # Diferentes formatos
        formats = [
            random_date.strftime("%d/%m/%Y"),  # 15/06/1985
            random_date.strftime("%d-%m-%Y"),  # 15-06-1985
            f"{random_date.day} de {self.get_month_name(random_date.month)} de {random_date.year}",  # 15 de junho de 1985
            random_date.strftime("%d/%m/%y"),  # 15/06/85
        ]

        formato_exibicao = random.choice(formats)
        formato_api = random_date.strftime("%Y%m%d")  # 19850615

        return formato_exibicao, formato_api

    def get_month_name(self, month: int) -> str:
        """Retorna nome do mês em português"""
        months = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
            5: "maio", 6: "junho", 7: "julho", 8: "agosto",
            9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
        }
        return months[month]

    def formatar_cpf(self, cpf: str, com_formatacao: bool = False) -> str:
        """Formata CPF com ou sem pontuação"""
        if com_formatacao and random.random() > 0.5:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    def gerar_conversa_saudacao(self) -> Dict:
        """Gera conversa de saudação simples"""
        saudacao = random.choice(self.saudacoes)
        resposta = random.choice(self.respostas_saudacao)

        return {
            "messages": [
                {"role": "user", "content": saudacao},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_consulta_sem_dados(self) -> Dict:
        """Gera conversa onde usuário pede consulta sem fornecer dados"""
        pedido = random.choice(self.pedidos_consulta)
        resposta = random.choice(self.respostas_pedir_dados)

        return {
            "messages": [
                {"role": "user", "content": pedido},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_dados_parciais_cpf(self) -> Dict:
        """Gera conversa com apenas CPF fornecido"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf, random.choice([True, False]))

        forma = random.choice(self.formas_cpf)
        mensagem_cpf = forma.format(cpf=cpf_formatado)
        resposta = random.choice(self.respostas_pedir_data)

        return {
            "messages": [
                {"role": "user", "content": mensagem_cpf},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_dados_parciais_data(self) -> Dict:
        """Gera conversa com apenas data fornecida"""
        data_exibicao, _ = self.gerar_data_nascimento()

        forma = random.choice(self.formas_data)
        mensagem_data = forma.format(data=data_exibicao)
        resposta = random.choice(self.respostas_pedir_cpf)

        return {
            "messages": [
                {"role": "user", "content": mensagem_data},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_consulta_completa(self) -> Dict:
        """Gera conversa com CPF e data juntos - DEVE chamar tool"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf, random.choice([True, False]))
        data_exibicao, data_api = self.gerar_data_nascimento()
        cidade = random.choice(self.cidades)

        # Diferentes formas de fornecer ambos os dados
        templates = [
            f"meu cpf é {cpf_formatado} e nasci em {data_exibicao}",
            f"cpf {cpf_formatado}, data nascimento {data_exibicao}",
            f"CPF: {cpf_formatado}, nascimento: {data_exibicao}",
            f"quero consultar o cpf {cpf_formatado}, nascido em {data_exibicao}",
            f"verifica o cpf {cpf_formatado}, data {data_exibicao}",
            f"{cpf_formatado} nascido em {data_exibicao}",
            f"consulta aí: {cpf_formatado} - {data_exibicao}"
        ]

        mensagem = random.choice(templates)

        # Adiciona cidade ocasionalmente
        if random.random() > 0.7:
            mensagem += f" em {cidade}"

        return {
            "messages": [
                {"role": "user", "content": mensagem},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": f"call_{random.randint(1000000, 9999999)}",
                        "type": "function",
                        "function": {
                            "name": "unimed_consult",
                            "arguments": json.dumps({
                                "cpf": cpf,
                                "data_nascimento": data_api,
                                "cidade": f"{cidade}_Tasy" if random.random() > 0.5 else "Natal_Tasy",
                                "tipo": "Contratos",
                                "protocolo": "0"
                            })
                        }
                    }]
                }
            ]
        }

    def gerar_conversa_multiplos_turnos(self) -> Dict:
        """Gera conversa completa com múltiplos turnos"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf, random.choice([True, False]))
        data_exibicao, data_api = self.gerar_data_nascimento()

        messages = []

        # Turno 1: Saudação
        saudacao = random.choice(self.saudacoes)
        messages.extend([
            {"role": "user", "content": saudacao},
            {"role": "assistant", "content": random.choice(self.respostas_saudacao)}
        ])

        # Turno 2: Pedido de consulta
        pedido = random.choice(self.pedidos_consulta)
        messages.extend([
            {"role": "user", "content": pedido},
            {"role": "assistant", "content": random.choice(self.respostas_pedir_dados)}
        ])

        # Turno 3 e 4: Fornece dados separadamente (50% das vezes)
        if random.random() > 0.5:
            # CPF primeiro
            forma_cpf = random.choice(self.formas_cpf)
            messages.extend([
                {"role": "user", "content": forma_cpf.format(cpf=cpf_formatado)},
                {"role": "assistant", "content": random.choice(self.respostas_pedir_data)}
            ])

            # Depois data
            forma_data = random.choice(self.formas_data)
            messages.extend([
                {"role": "user", "content": forma_data.format(data=data_exibicao)},
                {"role": "assistant", "content": None, "tool_calls": [{
                    "id": f"call_{random.randint(1000000, 9999999)}",
                    "type": "function",
                    "function": {
                        "name": "unimed_consult",
                        "arguments": json.dumps({
                            "cpf": cpf,
                            "data_nascimento": data_api,
                            "cidade": "Natal_Tasy",
                            "tipo": "Contratos",
                            "protocolo": "0"
                        })
                    }
                }]}
            ])
        else:
            # Fornece ambos juntos
            mensagem = f"CPF {cpf_formatado} e nasci em {data_exibicao}"
            messages.extend([
                {"role": "user", "content": mensagem},
                {"role": "assistant", "content": None, "tool_calls": [{
                    "id": f"call_{random.randint(1000000, 9999999)}",
                    "type": "function",
                    "function": {
                        "name": "unimed_consult",
                        "arguments": json.dumps({
                            "cpf": cpf,
                            "data_nascimento": data_api,
                            "cidade": "Natal_Tasy",
                            "tipo": "Contratos",
                            "protocolo": "0"
                        })
                    }
                }]}
            ])

        return {"messages": messages}

    def gerar_conversa_pergunta_frequente(self) -> Dict:
        """Gera conversa com pergunta frequente"""
        pergunta, resposta = random.choice(self.perguntas_frequentes)

        # Adiciona variação na pergunta
        if random.random() > 0.5:
            pergunta = pergunta.capitalize()

        return {
            "messages": [
                {"role": "user", "content": pergunta},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_dataset(self, total: int = 10000) -> List[Dict]:
        """Gera dataset completo com distribuição realista"""
        dataset = []

        # Distribuição dos tipos de conversa
        distribution = {
            'saudacao': int(total * 0.15),              # 15% - 1500
            'consulta_sem_dados': int(total * 0.15),    # 15% - 1500
            'dados_parciais_cpf': int(total * 0.10),    # 10% - 1000
            'dados_parciais_data': int(total * 0.10),   # 10% - 1000
            'consulta_completa': int(total * 0.25),     # 25% - 2500
            'multiplos_turnos': int(total * 0.15),      # 15% - 1500
            'pergunta_frequente': int(total * 0.10),    # 10% - 1000
        }

        # Gera cada tipo
        for conv_type, count in distribution.items():
            print(f"Gerando {count} conversas do tipo: {conv_type}")

            for i in range(count):
                if conv_type == 'saudacao':
                    conv = self.gerar_conversa_saudacao()
                elif conv_type == 'consulta_sem_dados':
                    conv = self.gerar_conversa_consulta_sem_dados()
                elif conv_type == 'dados_parciais_cpf':
                    conv = self.gerar_conversa_dados_parciais_cpf()
                elif conv_type == 'dados_parciais_data':
                    conv = self.gerar_conversa_dados_parciais_data()
                elif conv_type == 'consulta_completa':
                    conv = self.gerar_conversa_consulta_completa()
                elif conv_type == 'multiplos_turnos':
                    conv = self.gerar_conversa_multiplos_turnos()
                elif conv_type == 'pergunta_frequente':
                    conv = self.gerar_conversa_pergunta_frequente()

                # Adiciona metadata
                conv['metadata'] = {
                    'type': conv_type,
                    'id': f"{conv_type}_{i:05d}",
                    'timestamp': datetime.now().isoformat()
                }

                dataset.append(conv)

        # Embaralha para treino
        random.shuffle(dataset)

        return dataset

    def validar_dataset(self, dataset: List[Dict]) -> Dict:
        """Valida e gera estatísticas do dataset"""
        stats = {
            'total': len(dataset),
            'com_tool_calls': 0,
            'sem_tool_calls': 0,
            'turnos_por_conversa': [],
            'tipos': {}
        }

        for conv in dataset:
            # Conta turnos
            stats['turnos_por_conversa'].append(len(conv['messages']))

            # Verifica tool calls
            has_tool = any(
                msg.get('tool_calls')
                for msg in conv['messages']
                if msg.get('role') == 'assistant'
            )

            if has_tool:
                stats['com_tool_calls'] += 1
            else:
                stats['sem_tool_calls'] += 1

            # Conta tipos
            conv_type = conv.get('metadata', {}).get('type', 'unknown')
            stats['tipos'][conv_type] = stats['tipos'].get(conv_type, 0) + 1

        # Calcula médias
        stats['media_turnos'] = sum(stats['turnos_por_conversa']) / len(stats['turnos_por_conversa'])
        stats['percentual_com_tools'] = (stats['com_tool_calls'] / stats['total']) * 100

        return stats

def main():
    """Gera e salva o dataset"""
    print("=" * 60)
    print("🚀 GERADOR DE DATASET UNIMED")
    print("=" * 60)

    generator = UnimedDatasetGenerator()

    # Gera dataset
    print("\n📊 Gerando 10.000 conversas...")
    dataset = generator.gerar_dataset(10000)

    # Valida
    print("\n✅ Validando dataset...")
    stats = generator.validar_dataset(dataset)

    # Salva dataset completo
    with open('unimed_dataset_10k.jsonl', 'w', encoding='utf-8') as f:
        for conv in dataset:
            f.write(json.dumps(conv, ensure_ascii=False) + '\n')

    # Salva amostra para revisão
    with open('unimed_dataset_sample.jsonl', 'w', encoding='utf-8') as f:
        for conv in dataset[:100]:
            f.write(json.dumps(conv, ensure_ascii=False, indent=2) + '\n')

    # Exibe estatísticas
    print("\n📈 ESTATÍSTICAS DO DATASET:")
    print("-" * 40)
    print(f"Total de conversas: {stats['total']}")
    print(f"Com tool calls: {stats['com_tool_calls']} ({stats['percentual_com_tools']:.1f}%)")
    print(f"Sem tool calls: {stats['sem_tool_calls']}")
    print(f"Média de turnos: {stats['media_turnos']:.1f}")
    print("\nDistribuição por tipo:")
    for tipo, count in stats['tipos'].items():
        print(f"  • {tipo}: {count} ({count/stats['total']*100:.1f}%)")

    print("\n✅ Dataset salvo em:")
    print("  • unimed_dataset_10k.jsonl (completo)")
    print("  • unimed_dataset_sample.jsonl (amostra)")

    # Exemplos de validação
    print("\n📝 EXEMPLOS DO DATASET:")
    print("-" * 40)
    for i, conv in enumerate(dataset[:3], 1):
        print(f"\nExemplo {i} ({conv['metadata']['type']}):")
        for msg in conv['messages'][:2]:  # Primeiras 2 mensagens
            if msg.get('content'):
                role = "User" if msg['role'] == 'user' else "Assistant"
                content = msg['content'][:80] + '...' if len(msg.get('content', '')) > 80 else msg['content']
                print(f"  {role}: {content}")
            elif msg.get('tool_calls'):
                print(f"  Assistant: [CHAMADA DE FERRAMENTA]")

if __name__ == "__main__":
    main()