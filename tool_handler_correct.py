"""
Handler correto para ferramentas LLM com decisão semântica
"""

import json
import requests
from typing import Dict, List, Any, Optional

class ToolHandler:
    """Gerenciador de ferramentas para LLM com decisão semântica correta"""

    def __init__(self, api_url: str, auth_token: str):
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        }

    def unimed_consult(self, **kwargs):
        """Executa consulta real na API Unimed"""
        base_url = kwargs.get('base_url', 'https://unimed-central-cobranca.paneas.net/api/v1')
        cidade = kwargs['cidade']
        cpf = kwargs['cpf']
        data_nascimento = kwargs['data_nascimento']
        tipo = kwargs.get('tipo', 'Contratos')
        protocolo = kwargs.get('protocolo', '0')

        # Aqui faria a chamada real à API Unimed
        url = f"{base_url}/{cidade}/{tipo}/{protocolo}/{cpf}/{data_nascimento}"

        # Simulação de resposta
        return {
            "status": "success",
            "data": {
                "beneficiario": cpf,
                "contratos": ["123456", "789012"],
                "status": "ativo"
            }
        }

    def chat_with_tools(self, messages: List[Dict], use_tools: bool = True):
        """
        Envia chat para LLM com suporte a ferramentas

        Args:
            messages: Lista de mensagens do chat
            use_tools: Se deve incluir ferramentas disponíveis
        """

        # Definição das ferramentas disponíveis
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "unimed_consult",
                    "description": "Consulta dados de beneficiário e contratos na API Unimed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_url": {
                                "type": "string",
                                "description": "URL base da API Unimed",
                                "default": "https://unimed-central-cobranca.paneas.net/api/v1"
                            },
                            "cidade": {
                                "type": "string",
                                "description": "Cidade do protocolo (ex: Natal_Tasy)"
                            },
                            "tipo": {
                                "type": "string",
                                "description": "Tipo de consulta (ex: Contratos)",
                                "default": "Contratos"
                            },
                            "protocolo": {
                                "type": "string",
                                "description": "Número do protocolo (opcional, use 0 ou null para ignorar)"
                            },
                            "cpf": {
                                "type": "string",
                                "description": "CPF do beneficiário"
                            },
                            "data_nascimento": {
                                "type": "string",
                                "description": "Data de nascimento (formato: AAAA-MM-DD ou AAAAMMDD)"
                            }
                        },
                        "required": ["cidade", "cpf", "data_nascimento"]
                    }
                }
            }
        ]

        # Construir payload
        payload = {
            "model": "paneas-q32b",
            "messages": messages
        }

        # Adicionar tools apenas se necessário
        if use_tools:
            payload["tools"] = tools
            # NÃO forçar tool_choice - deixar o modelo decidir!
            # Opcionalmente, pode usar "tool_choice": "auto" (padrão)
            payload["tool_choice"] = "auto"  # ou omitir completamente

        # Fazer chamada à API
        response = requests.post(
            f"{self.api_url}/chat/completions",
            headers=self.headers,
            json=payload
        )

        return response.json()

    def process_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """Processa e executa chamadas de ferramentas"""
        results = []

        for call in tool_calls:
            function_name = call["function"]["name"]
            arguments = json.loads(call["function"]["arguments"])

            # Executar a função apropriada
            if function_name == "unimed_consult":
                result = self.unimed_consult(**arguments)
            else:
                result = {"error": f"Função {function_name} não encontrada"}

            results.append({
                "tool_call_id": call["id"],
                "role": "tool",
                "name": function_name,
                "content": json.dumps(result)
            })

        return results

    def complete_conversation(self, user_input: str) -> str:
        """
        Fluxo completo de conversa com suporte a ferramentas

        Args:
            user_input: Entrada do usuário

        Returns:
            Resposta final do modelo
        """
        # Passo 1: Enviar mensagem do usuário
        messages = [{"role": "user", "content": user_input}]

        # Passo 2: Obter resposta do modelo (pode incluir tool_calls)
        response = self.chat_with_tools(messages)

        # Passo 3: Verificar se há tool_calls
        if response["choices"][0].get("message", {}).get("tool_calls"):
            tool_calls = response["choices"][0]["message"]["tool_calls"]

            # Passo 4: Executar as ferramentas
            tool_results = self.process_tool_calls(tool_calls)

            # Passo 5: Adicionar resultados à conversa
            messages.append(response["choices"][0]["message"])  # Adiciona a mensagem com tool_calls
            messages.extend(tool_results)  # Adiciona os resultados das tools

            # Passo 6: Obter resposta final do modelo
            final_response = self.chat_with_tools(messages, use_tools=False)
            return final_response["choices"][0]["message"]["content"]
        else:
            # Não precisou de ferramentas, retornar resposta direta
            return response["choices"][0]["message"]["content"]


# Exemplos de uso correto
if __name__ == "__main__":
    handler = ToolHandler(
        api_url="https://jota.ngrok.app/api/v1",
        auth_token="token_abc123"
    )

    print("=" * 60)
    print("SIMULAÇÃO DE CONVERSAS COM USO CORRETO DE TOOLS")
    print("=" * 60)

    # Cenário 1: Saudação simples (NÃO deve chamar tool)
    print("\n📝 Cenário 1: Saudação simples")
    print("User: 'Oi'")
    print("Expectativa: Resposta de saudação, SEM tool_call")
    print("Payload enviado:")
    print(json.dumps({
        "model": "paneas-q32b",
        "messages": [{"role": "user", "content": "Oi"}],
        "tools": "[...definições das tools...]",
        "tool_choice": "auto"  # Deixa o modelo decidir!
    }, indent=2))
    print("\nResposta esperada: 'Olá! Como posso ajudar você hoje?'")

    # Cenário 2: Pergunta sobre Unimed (DEVE chamar tool)
    print("\n" + "=" * 60)
    print("📝 Cenário 2: Consulta Unimed")
    print("User: 'Quero consultar o contrato do CPF 00835690490, nascido em 28/03/1979 em Natal'")
    print("Expectativa: DEVE gerar tool_call")
    print("\nFluxo esperado:")
    print("1. Modelo detecta necessidade da tool")
    print("2. Modelo gera tool_call com argumentos extraídos:")
    print(json.dumps({
        "tool_calls": [{
            "type": "function",
            "function": {
                "name": "unimed_consult",
                "arguments": json.dumps({
                    "cidade": "Natal_Tasy",
                    "cpf": "00835690490",
                    "data_nascimento": "19790328"
                })
            }
        }]
    }, indent=2))
    print("3. Sistema executa a função Python real")
    print("4. Resultado retorna ao modelo")
    print("5. Modelo gera resposta final humanizada")

    # Cenário 3: Pergunta genérica (NÃO deve chamar tool)
    print("\n" + "=" * 60)
    print("📝 Cenário 3: Pergunta genérica")
    print("User: 'Qual a capital do Brasil?'")
    print("Expectativa: Resposta direta, SEM tool_call")
    print("Resposta esperada: 'A capital do Brasil é Brasília.'")