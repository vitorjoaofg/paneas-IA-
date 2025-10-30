#!/usr/bin/env python3
"""
Gerador de Dataset ULTRA REALISTA - 100k conversas
Simula conversas reais de atendimento Unimed com:
- Erros de digitação
- Linguagem coloquial
- Casos complexos
- Múltiplos contextos
"""

import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import string

class RealisticUnimedDatasetGenerator:
    """Gerador ultra-realista de conversas para LoRA"""

    def __init__(self):
        # Nomes brasileiros reais (mais variados)
        self.nomes = [
            "João Silva", "Maria Santos", "José Oliveira", "Ana Costa", "Pedro Souza",
            "Juliana Lima", "Carlos Ferreira", "Patricia Alves", "Lucas Pereira",
            "Fernanda Rodrigues", "Rafael Gomes", "Camila Martins", "Bruno Ribeiro",
            "Amanda Carvalho", "Marcos Almeida", "Beatriz Dias", "Gabriel Santos",
            "Larissa Oliveira", "Thiago Costa", "Leticia Souza", "Matheus Lima",
            "Isabela Ferreira", "Diego Alves", "Natalia Pereira", "Ricardo Rodrigues",
            "Mariana Gomes", "Felipe Martins", "Carolina Ribeiro", "Eduardo Carvalho",
            "Vanessa Almeida", "Leonardo Dias", "Aline Santos", "Gustavo Oliveira",
            "Daniela Costa", "Rodrigo Souza", "Jessica Lima", "Alexandre Ferreira",
            "Priscila Alves", "Henrique Pereira", "Tatiana Rodrigues", "Vinicius Gomes"
        ]

        self.sobrenomes_extras = [
            "da Silva", "dos Santos", "de Oliveira", "da Costa", "de Souza",
            "Nascimento", "Barbosa", "Rocha", "Correia", "Araújo", "Mendes",
            "Barros", "Freitas", "Cardoso", "Nunes", "Moreira", "Cavalcanti"
        ]

        # Cidades do RN
        self.cidades = [
            "Natal", "Parnamirim", "Mossoró", "São Gonçalo do Amarante",
            "Macaíba", "Ceará-Mirim", "Caicó", "Assu", "Currais Novos"
        ]

        # Saudações variadas (incluindo erros de digitação comuns)
        self.saudacoes = [
            "oi", "ola", "olá", "oii", "oiii", "oie",
            "bom dia", "boa tarde", "boa noite",
            "bom dia!", "boa tarde!", "boa noite!",
            "oi, tudo bem?", "oi tudo bem", "oi td bem",
            "ola boa tarde", "olá, boa tarde", "oi boa tarde",
            "alô", "alo", "alou", "alow",
            "ei", "eii", "eiii", "hey",
            "opa", "opaa", "e ai", "e aí",
            "fala", "salve", "iai", "iaí",
            "bom dia, tudo bem?", "bd", "bt", "bn",
            "oi preciso de ajuda", "ola preciso de ajuda",
            "oi vc pode me ajudar", "oi vcs podem me ajudar"
        ]

        # Pedidos de consulta mais variados
        self.pedidos_consulta = [
            "preciso ver meu contrato",
            "quero consultar meu plano",
            "pode verificar meus dados?",
            "gostaria de ver meu contrato",
            "preciso consultar minha carteirinha",
            "quero ver meus benefícios",
            "pode checar meu plano?",
            "verifica meu contrato por favor",
            "me mostra meu contrato",
            "consulta meu plano aí",
            "queria saber sobre meu plano",
            "como ta meu contrato",
            "quero saber do meu plano",
            "ve meu contrato ai",
            "olha meu plano pra mim",
            "confere meus dados",
            "da uma olhada no meu contrato",
            "preciso de informações do plano",
            "me passa os dados do meu contrato",
            "qual meu plano mesmo?",
            "que plano eu tenho?",
            "meu plano ta ativo?",
            "quero ver se ta tudo certo com meu plano",
            "preciso conferir uma coisa no meu contrato"
        ]

        # Formas de fornecer CPF (com variações e erros)
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
            "anota aí: {cpf}",
            "o numero é {cpf}",
            "cpf e {cpf}",  # erro de digitação
            "cf {cpf}",  # abreviado errado
            "meu cpf e o seguinte {cpf}",
            "documento {cpf}",
            "CPF {cpf}",
            "ta aqui {cpf}",
            "o cpf {cpf}",
            "numero do cpf {cpf}"
        ]

        # Formas de fornecer data (com variações)
        self.formas_data = [
            "nasci em {data}",
            "data de nascimento {data}",
            "{data}",
            "nascimento: {data}",
            "nasci dia {data}",
            "minha data de nascimento é {data}",
            "data nascimento {data}",
            "nascido em {data}",
            "data {data}",
            "nascimento {data}",
            "aniversario {data}",
            "naci em {data}",  # erro
            "é {data}",
            "dia {data}",
            "nascido dia {data}",
            "faco aniversario em {data}",
            "data de nasc {data}",
            "dt nascimento {data}",
            "nascido no dia {data}"
        ]

        # Perguntas frequentes expandidas
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
            ("tem desconto?", "Oferecemos descontos para pagamento anual à vista e planos empresariais. Consulte condições."),
            ("aceita qual cartao?", "Aceitamos todos os cartões de crédito: Visa, Mastercard, Elo, Amex, Hipercard."),
            ("como cancelar o plano?", "Para cancelar, você deve comparecer pessoalmente em uma de nossas unidades com documento e último boleto pago."),
            ("segunda via do boleto", "Segunda via pode ser emitida pelo app, site ou telefone (84) 4020-8900."),
            ("esqueci minha senha", "Para recuperar senha do app, clique em 'Esqueci minha senha' na tela de login ou ligue (84) 4020-8900."),
            ("reembolso como funciona?", "Reembolsos devem ser solicitados em até 12 meses com nota fiscal e relatório médico. Análise em até 30 dias."),
            ("rede credenciada", "Consulte a rede credenciada completa no app Unimed Natal ou site www.unimednatal.com.br"),
            ("autorização de exame", "Autorizações de exames podem ser solicitadas pelo app, site ou presencialmente. Prazo de 48h para análise."),
            ("carteirinha digital", "A carteirinha digital está disponível no app Unimed Natal. Baixe na Play Store ou App Store."),
            ("mudança de plano", "Mudanças de plano podem ser solicitadas anualmente no mês de aniversário do contrato."),
            ("coparticipação", "Planos com coparticipação cobram 30% do valor de consultas e 50% de exames. Valores no site.")
        ]

        # Reclamações comuns
        self.reclamacoes = [
            "to tentando marcar consulta ha dias",
            "ninguem me atende no telefone",
            "o aplicativo nao funciona",
            "meu boleto nao chegou",
            "a autorizacao ta demorando muito",
            "o medico nao ta atendendo unimed",
            "cobraram errado no meu boleto",
            "nao consigo acessar o app",
            "perdi minha carteirinha",
            "o hospital nao aceitou meu plano"
        ]

        # Respostas do assistente (mais variadas e naturais)
        self.respostas_saudacao = [
            "Olá! Bem-vindo ao atendimento Unimed Natal. Como posso ajudá-lo hoje?",
            "Oi! Sou do atendimento Unimed Natal. Em que posso ajudar?",
            "Bom dia! É um prazer atendê-lo. Como posso auxiliar com seu plano Unimed?",
            "Boa tarde! Unimed Natal, como posso ser útil?",
            "Olá! Como posso ajudá-lo com seu plano de saúde hoje?",
            "Oi! Seja bem-vindo à Unimed Natal. Como posso auxiliar?",
            "Olá! Aqui é da Unimed Natal. Em que posso ajudar você hoje?",
            "Oi! Bem-vindo ao nosso atendimento. Como posso ajudar?",
            "Bom dia! Unimed Natal ao seu dispor. Como posso auxiliar?",
            "Boa tarde! É um prazer atendê-lo. Em que posso ajudar?"
        ]

        self.respostas_pedir_dados = [
            "Para consultar seus dados, vou precisar do seu CPF e data de nascimento. Pode me informar?",
            "Claro! Para acessar seu contrato, preciso do CPF e data de nascimento. Por favor, forneça essas informações.",
            "Posso verificar sim! Me informe seu CPF e data de nascimento para consultar.",
            "Para prosseguir com a consulta, preciso que me forneça seu CPF e data de nascimento.",
            "Vou consultar seus dados. Por favor, me informe CPF e data de nascimento.",
            "Certo! Preciso do seu CPF e data de nascimento para acessar suas informações.",
            "Com certeza! Para verificar seu contrato, preciso do CPF e data de nascimento.",
            "Vou verificar isso para você. Preciso do seu CPF e data de nascimento, por favor.",
            "Para acessar suas informações, vou precisar do CPF e data de nascimento.",
            "Claro que posso ajudar! Me passa seu CPF e data de nascimento?"
        ]

        # Casos de erro/problema
        self.mensagens_erro = [
            "nao to conseguindo entrar",
            "ta dando erro",
            "nao funciona",
            "sistema fora do ar?",
            "site nao abre",
            "aplicativo travou"
        ]

        # Despedidas
        self.despedidas = [
            "obrigado", "obrigada", "valeu", "vlw",
            "tchau", "até logo", "ate logo", "ate mais",
            "abraços", "abs", "falou", "flw",
            "muito obrigado", "obrigado pela ajuda",
            "era só isso", "era isso", "só isso",
            "ok obrigado", "ok valeu", "beleza valeu"
        ]

    def adicionar_erro_digitacao(self, texto: str, probabilidade: float = 0.1) -> str:
        """Adiciona erros de digitação realistas"""
        if random.random() > probabilidade:
            return texto

        erro_tipo = random.choice(['trocar', 'omitir', 'duplicar', 'espaço'])

        if erro_tipo == 'trocar' and len(texto) > 1:
            # Troca letras adjacentes
            pos = random.randint(0, len(texto) - 2)
            texto = texto[:pos] + texto[pos+1] + texto[pos] + texto[pos+2:]
        elif erro_tipo == 'omitir' and len(texto) > 2:
            # Omite uma letra
            pos = random.randint(1, len(texto) - 1)
            texto = texto[:pos] + texto[pos+1:]
        elif erro_tipo == 'duplicar' and len(texto) > 0:
            # Duplica uma letra
            pos = random.randint(0, len(texto) - 1)
            texto = texto[:pos] + texto[pos] + texto[pos] + texto[pos+1:]
        elif erro_tipo == 'espaço':
            # Remove espaço ou adiciona espaço extra
            texto = texto.replace(' ', '  ') if random.random() > 0.5 else texto.replace(' ', '')

        return texto

    def gerar_cpf(self) -> str:
        """Gera CPF válido"""
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
        """Gera data de nascimento em vários formatos"""
        start_date = datetime(1940, 1, 1)
        end_date = datetime(2006, 12, 31)
        random_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))

        # Múltiplos formatos realistas
        formats = [
            random_date.strftime("%d/%m/%Y"),  # 15/06/1985
            random_date.strftime("%d/%m/%y"),  # 15/06/85
            random_date.strftime("%d-%m-%Y"),  # 15-06-1985
            random_date.strftime("%d.%m.%Y"),  # 15.06.1985
            f"{random_date.day}/{random_date.month}/{random_date.year}",  # 15/6/1985 (sem zero)
            f"{random_date.day} de {self.get_month_name(random_date.month)} de {random_date.year}",
            f"{random_date.day}/{self.get_month_abbr(random_date.month)}/{random_date.year}",  # 15/jun/1985
            random_date.strftime("%d%m%Y"),  # 15061985 (sem separador)
        ]

        formato_exibicao = random.choice(formats)
        formato_api = random_date.strftime("%Y%m%d")

        return formato_exibicao, formato_api

    def get_month_name(self, month: int) -> str:
        """Nome do mês em português"""
        months = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
            5: "maio", 6: "junho", 7: "julho", 8: "agosto",
            9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
        }
        return months[month]

    def get_month_abbr(self, month: int) -> str:
        """Abreviação do mês"""
        abbr = {
            1: "jan", 2: "fev", 3: "mar", 4: "abr",
            5: "mai", 6: "jun", 7: "jul", 8: "ago",
            9: "set", 10: "out", 11: "nov", 12: "dez"
        }
        return abbr[month]

    def formatar_cpf(self, cpf: str, com_formatacao: bool = None) -> str:
        """Formata CPF com diferentes estilos"""
        if com_formatacao is None:
            com_formatacao = random.random() > 0.5

        if not com_formatacao:
            return cpf

        formato = random.choice([
            f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}",  # 123.456.789-01
            f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}/{cpf[9:]}",  # 123.456.789/01
            f"{cpf[:3]} {cpf[3:6]} {cpf[6:9]} {cpf[9:]}",  # 123 456 789 01
            f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}.{cpf[9:]}"   # 123.456.789.01
        ])
        return formato

    def gerar_conversa_saudacao(self) -> Dict:
        """Saudação com variações"""
        saudacao = random.choice(self.saudacoes)
        if random.random() < 0.15:
            saudacao = self.adicionar_erro_digitacao(saudacao)

        resposta = random.choice(self.respostas_saudacao)

        return {
            "messages": [
                {"role": "user", "content": saudacao},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_consulta_completa(self) -> Dict:
        """Consulta com dados completos"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf)
        data_exibicao, data_api = self.gerar_data_nascimento()
        cidade = random.choice(self.cidades)

        # Templates mais realistas
        templates = [
            f"meu cpf é {cpf_formatado} e nasci em {data_exibicao}",
            f"cpf {cpf_formatado}, data nascimento {data_exibicao}",
            f"CPF: {cpf_formatado}, nascimento: {data_exibicao}",
            f"quero consultar o cpf {cpf_formatado}, nascido em {data_exibicao}",
            f"verifica o cpf {cpf_formatado}, data {data_exibicao}",
            f"{cpf_formatado} nascido em {data_exibicao}",
            f"consulta aí: {cpf_formatado} - {data_exibicao}",
            f"cpf {cpf_formatado} nascimento {data_exibicao}",
            f"o cpf e {cpf_formatado} nasci {data_exibicao}",
            f"documento {cpf_formatado}, {data_exibicao}",
            f"cpf {cpf_formatado}\ndata {data_exibicao}",
            f"cpf {cpf_formatado}\nnascimento {data_exibicao}",
            f"{cpf_formatado}, {data_exibicao}",
            f"pode consultar o cpf {cpf_formatado} nascimento {data_exibicao}",
            f"verifica pra mim cpf {cpf_formatado} dt nasc {data_exibicao}"
        ]

        mensagem = random.choice(templates)

        # Adiciona cidade ocasionalmente
        if random.random() > 0.6:
            if random.random() > 0.5:
                mensagem += f" em {cidade}"
            else:
                mensagem += f", {cidade}"

        # Adiciona erro de digitação ocasionalmente
        if random.random() < 0.1:
            mensagem = self.adicionar_erro_digitacao(mensagem, 0.3)

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
                                "cidade": f"{cidade}_Tasy" if cidade != "Natal" else "Natal_Tasy",
                                "tipo": "Contratos",
                                "protocolo": "0"
                            })
                        }
                    }]
                }
            ]
        }

    def gerar_conversa_complexa(self) -> Dict:
        """Conversas mais complexas e realistas"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf)
        data_exibicao, data_api = self.gerar_data_nascimento()
        nome = random.choice(self.nomes)

        messages = []

        # Início variado
        inicio_tipos = ['saudacao', 'direto', 'problema', 'duvida']
        tipo_inicio = random.choice(inicio_tipos)

        if tipo_inicio == 'saudacao':
            messages.extend([
                {"role": "user", "content": random.choice(self.saudacoes)},
                {"role": "assistant", "content": random.choice(self.respostas_saudacao)}
            ])

        elif tipo_inicio == 'problema':
            problema = random.choice(self.reclamacoes)
            messages.extend([
                {"role": "user", "content": problema},
                {"role": "assistant", "content": "Entendo sua frustração. Vou verificar isso para você. Preciso do seu CPF e data de nascimento para acessar seus dados."}
            ])

        elif tipo_inicio == 'duvida':
            duvida = random.choice([
                "tenho uma duvida",
                "preciso tirar uma duvida",
                "me tira uma duvida",
                "queria saber uma coisa"
            ])
            messages.extend([
                {"role": "user", "content": duvida},
                {"role": "assistant", "content": "Claro! Estou aqui para esclarecer suas dúvidas. Como posso ajudar?"}
            ])

        # Pedido principal
        pedido = random.choice(self.pedidos_consulta)
        if random.random() < 0.1:
            pedido = self.adicionar_erro_digitacao(pedido)

        messages.extend([
            {"role": "user", "content": pedido},
            {"role": "assistant", "content": random.choice(self.respostas_pedir_dados)}
        ])

        # Fornecimento dos dados (várias formas)
        forma_fornecer = random.choice(['junto', 'separado', 'confuso', 'com_nome'])

        if forma_fornecer == 'junto':
            msg = f"cpf {cpf_formatado} nascimento {data_exibicao}"
            messages.extend([
                {"role": "user", "content": msg},
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

        elif forma_fornecer == 'separado':
            # CPF primeiro
            forma_cpf = random.choice(self.formas_cpf)
            messages.extend([
                {"role": "user", "content": forma_cpf.format(cpf=cpf_formatado)},
                {"role": "assistant", "content": "Obrigado pelo CPF. Agora preciso também da sua data de nascimento."}
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

        elif forma_fornecer == 'confuso':
            # Mensagem confusa mas com dados
            msgs_confusas = [
                f"olha o cpf é esse aqui {cpf_formatado} e eu nasci {data_exibicao} pode ver?",
                f"é... o cpf {cpf_formatado}, nasci em {data_exibicao}... ta certo?",
                f"deixa eu ver... cpf {cpf_formatado} e a data é {data_exibicao}",
                f"anota ai cpf {cpf_formatado} nascimento {data_exibicao} é isso",
                f"cpf {cpf_formatado} data {data_exibicao} acho que é isso"
            ]
            messages.extend([
                {"role": "user", "content": random.choice(msgs_confusas)},
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

        elif forma_fornecer == 'com_nome':
            msg = f"meu nome é {nome}, cpf {cpf_formatado} e nasci em {data_exibicao}"
            messages.extend([
                {"role": "user", "content": msg},
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

        # Adiciona resposta após tool call (simula retorno)
        if messages[-1].get("tool_calls"):
            resultado_simulado = random.choice([
                f"Localizei seu contrato, Sr(a). {nome.split()[0]}. Você possui o plano Prata ativo desde 2020. Carteirinha válida até 12/2025.",
                f"Encontrei seus dados. Plano Ouro empresarial, ativo. Titular: {nome}. Sem pendências financeiras.",
                f"Contrato localizado! Plano Bronze familiar com 3 dependentes. Mensalidade em dia. Próximo vencimento: dia 10.",
                f"Seus dados: Plano Diamante, contrato ativo. Carência cumprida para todos os procedimentos."
            ])

            messages.append({
                "role": "tool",
                "content": json.dumps({"status": "success", "data": {"plano": "ativo"}}),
                "tool_call_id": messages[-1]["tool_calls"][0]["id"]
            })

            messages.append({
                "role": "assistant",
                "content": resultado_simulado
            })

            # Pergunta de follow-up ocasional
            if random.random() > 0.7:
                followup = random.choice([
                    "mais alguma coisa?",
                    "preciso de mais alguma informação?",
                    "posso ajudar com algo mais?",
                    "tem alguma dúvida sobre o plano?"
                ])
                messages.extend([
                    {"role": "user", "content": followup},
                    {"role": "assistant", "content": "Claro! O que você gostaria de saber?"}
                ])

        return {"messages": messages}

    def gerar_conversa_reclamacao(self) -> Dict:
        """Conversa com reclamação"""
        reclamacao = random.choice(self.reclamacoes)

        respostas_reclamacao = [
            "Sinto muito pelo transtorno. Vou verificar isso imediatamente para você. Preciso do seu CPF e data de nascimento.",
            "Peço desculpas pelo inconveniente. Vamos resolver isso agora. Me informe seu CPF e data de nascimento, por favor.",
            "Entendo sua frustração e vou ajudar a resolver. Para isso, preciso do CPF e data de nascimento.",
            "Lamento pelo problema. Vou verificar o que está acontecendo. Preciso dos seus dados: CPF e data de nascimento."
        ]

        return {
            "messages": [
                {"role": "user", "content": reclamacao},
                {"role": "assistant", "content": random.choice(respostas_reclamacao)}
            ]
        }

    def gerar_conversa_pergunta_frequente(self) -> Dict:
        """FAQ expandido"""
        pergunta, resposta = random.choice(self.perguntas_frequentes)

        # Adiciona variação na pergunta
        if random.random() > 0.7:
            pergunta = self.adicionar_erro_digitacao(pergunta, 0.2)

        # Varia capitalização
        if random.random() > 0.5:
            pergunta = pergunta.lower()

        return {
            "messages": [
                {"role": "user", "content": pergunta},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_despedida(self) -> Dict:
        """Conversas de despedida"""
        despedida = random.choice(self.despedidas)

        respostas_despedida = [
            "De nada! Se precisar de algo mais, estamos à disposição.",
            "Por nada! Qualquer dúvida, pode entrar em contato.",
            "Disponha! Tenha um ótimo dia!",
            "Foi um prazer ajudar! Até mais!",
            "Sempre à disposição! Bom dia!",
            "Que bom que pude ajudar! Até logo!",
            "Fico feliz em ter ajudado! Até a próxima!"
        ]

        return {
            "messages": [
                {"role": "user", "content": despedida},
                {"role": "assistant", "content": random.choice(respostas_despedida)}
            ]
        }

    def gerar_conversa_dados_incorretos(self) -> Dict:
        """Conversas com dados incorretos/incompletos"""
        casos = [
            # CPF inválido
            {
                "user": "meu cpf é 11111111111",
                "assistant": "O CPF informado parece estar incorreto. Por favor, verifique e informe novamente o número correto do seu CPF."
            },
            # Data futura
            {
                "user": "nasci em 15/06/2030",
                "assistant": "A data de nascimento informada está incorreta (data futura). Por favor, verifique e informe a data correta."
            },
            # Dados parciais confusos
            {
                "user": "meu cpf é... esqueci, mas nasci em janeiro",
                "assistant": "Preciso do número completo do CPF e da data de nascimento completa (dia/mês/ano) para prosseguir com a consulta."
            },
            # Apenas nome
            {
                "user": f"meu nome é {random.choice(self.nomes)}",
                "assistant": "Obrigado pelo nome. Para consultar seus dados, também preciso do CPF e data de nascimento."
            }
        ]

        caso = random.choice(casos)
        return {
            "messages": [
                {"role": "user", "content": caso["user"]},
                {"role": "assistant", "content": caso["assistant"]}
            ]
        }

    def gerar_dataset(self, total: int = 100000) -> List[Dict]:
        """Gera dataset de 100k conversas ultra-realistas"""
        dataset = []

        # Distribuição mais realista (100k)
        distribution = {
            'saudacao': int(total * 0.08),              # 8% - 8,000
            'consulta_sem_dados': int(total * 0.10),    # 10% - 10,000
            'dados_parciais_cpf': int(total * 0.08),    # 8% - 8,000
            'dados_parciais_data': int(total * 0.07),   # 7% - 7,000
            'consulta_completa': int(total * 0.20),     # 20% - 20,000
            'conversa_complexa': int(total * 0.15),     # 15% - 15,000
            'reclamacao': int(total * 0.08),            # 8% - 8,000
            'pergunta_frequente': int(total * 0.12),    # 12% - 12,000
            'despedida': int(total * 0.07),             # 7% - 7,000
            'dados_incorretos': int(total * 0.05),      # 5% - 5,000
        }

        print("\n📊 Gerando dataset realista...")
        for conv_type, count in distribution.items():
            print(f"  Gerando {count:,} conversas: {conv_type}")

            for i in range(count):
                if i % 1000 == 0 and i > 0:
                    print(f"    ... {i:,}/{count:,} ({i/count*100:.1f}%)")

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
                elif conv_type == 'conversa_complexa':
                    conv = self.gerar_conversa_complexa()
                elif conv_type == 'reclamacao':
                    conv = self.gerar_conversa_reclamacao()
                elif conv_type == 'pergunta_frequente':
                    conv = self.gerar_conversa_pergunta_frequente()
                elif conv_type == 'despedida':
                    conv = self.gerar_conversa_despedida()
                elif conv_type == 'dados_incorretos':
                    conv = self.gerar_conversa_dados_incorretos()

                # Metadata
                conv['metadata'] = {
                    'type': conv_type,
                    'id': f"{conv_type}_{i:06d}",
                    'timestamp': datetime.now().isoformat()
                }

                dataset.append(conv)

        # Embaralha
        print("\n🔀 Embaralhando dataset...")
        random.shuffle(dataset)

        return dataset

    def gerar_conversa_consulta_sem_dados(self) -> Dict:
        """Consulta sem fornecer dados"""
        pedido = random.choice(self.pedidos_consulta)
        if random.random() < 0.1:
            pedido = self.adicionar_erro_digitacao(pedido)

        resposta = random.choice(self.respostas_pedir_dados)

        return {
            "messages": [
                {"role": "user", "content": pedido},
                {"role": "assistant", "content": resposta}
            ]
        }

    def gerar_conversa_dados_parciais_cpf(self) -> Dict:
        """Apenas CPF fornecido"""
        cpf = self.gerar_cpf()
        cpf_formatado = self.formatar_cpf(cpf)

        forma = random.choice(self.formas_cpf)
        mensagem_cpf = forma.format(cpf=cpf_formatado)

        if random.random() < 0.1:
            mensagem_cpf = self.adicionar_erro_digitacao(mensagem_cpf)

        respostas = [
            "Obrigado pelo CPF. Agora preciso também da sua data de nascimento para continuar.",
            "Recebi o CPF. Pode me informar sua data de nascimento?",
            "Perfeito! Agora só falta a data de nascimento para completar a consulta.",
            "CPF anotado! Qual sua data de nascimento?",
            "Ok, já tenho o CPF. Me informe também quando você nasceu.",
            "Certo! Para continuar, preciso da sua data de nascimento."
        ]

        return {
            "messages": [
                {"role": "user", "content": mensagem_cpf},
                {"role": "assistant", "content": random.choice(respostas)}
            ]
        }

    def gerar_conversa_dados_parciais_data(self) -> Dict:
        """Apenas data fornecida"""
        data_exibicao, _ = self.gerar_data_nascimento()

        forma = random.choice(self.formas_data)
        mensagem_data = forma.format(data=data_exibicao)

        if random.random() < 0.1:
            mensagem_data = self.adicionar_erro_digitacao(mensagem_data)

        respostas = [
            "Obrigado pela data. Agora preciso do seu CPF para consultar.",
            "Data anotada! Pode me informar seu CPF?",
            "Perfeito! Agora só preciso do número do seu CPF.",
            "Ok, já anotei a data. Qual seu CPF?",
            "Recebi a data de nascimento. Me informe também seu CPF.",
            "Certo! Para prosseguir, preciso do número do seu CPF."
        ]

        return {
            "messages": [
                {"role": "user", "content": mensagem_data},
                {"role": "assistant", "content": random.choice(respostas)}
            ]
        }

def main():
    """Gera e salva dataset de 100k conversas"""
    print("=" * 80)
    print("🚀 GERADOR DE DATASET UNIMED - 100K CONVERSAS REALISTAS")
    print("=" * 80)

    generator = RealisticUnimedDatasetGenerator()

    # Gera dataset
    print("\n⏳ Iniciando geração de 100.000 conversas...")
    print("   Isso pode levar 5-10 minutos...")

    dataset = generator.gerar_dataset(100000)

    # Validação
    print("\n✅ Validando dataset...")
    stats = {
        'total': len(dataset),
        'com_tool_calls': 0,
        'sem_tool_calls': 0,
        'turnos_total': 0,
        'tipos': {}
    }

    for conv in dataset:
        stats['turnos_total'] += len(conv['messages'])

        has_tool = any(
            msg.get('tool_calls')
            for msg in conv['messages']
            if msg.get('role') == 'assistant'
        )

        if has_tool:
            stats['com_tool_calls'] += 1
        else:
            stats['sem_tool_calls'] += 1

        tipo = conv['metadata']['type']
        stats['tipos'][tipo] = stats['tipos'].get(tipo, 0) + 1

    # Salva dataset completo
    print("\n💾 Salvando arquivos...")
    with open('unimed_dataset_100k.jsonl', 'w', encoding='utf-8') as f:
        for conv in dataset:
            f.write(json.dumps(conv, ensure_ascii=False) + '\n')

    # Salva amostra
    with open('unimed_dataset_sample_100.jsonl', 'w', encoding='utf-8') as f:
        for conv in dataset[:100]:
            f.write(json.dumps(conv, ensure_ascii=False, indent=2) + '\n')

    # Estatísticas
    print("\n" + "=" * 80)
    print("📈 ESTATÍSTICAS DO DATASET")
    print("=" * 80)
    print(f"Total de conversas: {stats['total']:,}")
    print(f"Com tool calls: {stats['com_tool_calls']:,} ({stats['com_tool_calls']/stats['total']*100:.1f}%)")
    print(f"Sem tool calls: {stats['sem_tool_calls']:,}")
    print(f"Total de mensagens: {stats['turnos_total']:,}")
    print(f"Média turnos/conversa: {stats['turnos_total']/stats['total']:.1f}")

    print("\nDistribuição por tipo:")
    for tipo, count in sorted(stats['tipos'].items(), key=lambda x: x[1], reverse=True):
        print(f"  • {tipo}: {count:,} ({count/stats['total']*100:.1f}%)")

    print("\n✅ Dataset salvo:")
    print("  • unimed_dataset_100k.jsonl (completo - ~150MB)")
    print("  • unimed_dataset_sample_100.jsonl (amostra)")

    print("\n🎯 Dataset pronto para treinamento de LoRA!")

if __name__ == "__main__":
    main()