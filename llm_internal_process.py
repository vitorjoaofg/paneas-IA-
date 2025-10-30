#!/usr/bin/env python3
"""
Demonstração visual do processo interno do LLM ao decidir sobre tools
"""

import json
from typing import Dict, List, Tuple

class LLMToolDecisionSimulator:
    """Simula o processo de decisão interna do LLM"""

    def __init__(self):
        # Simulação de embeddings (valores fictícios para demonstração)
        self.tool_embeddings = {
            "unimed_consult": [0.8, 0.2, 0.9, 0.1, 0.7],  # "consulta", "dados", "cpf", "contrato"
            "weather": [0.1, 0.9, 0.2, 0.8, 0.3],         # "tempo", "clima", "temperatura"
            "calculator": [0.2, 0.1, 0.3, 0.9, 0.8]       # "calcular", "soma", "matemática"
        }

    def analyze_input(self, user_input: str):
        """Simula análise completa do input"""
        print("=" * 80)
        print(f"🔍 PROCESSO INTERNO DO LLM PARA: '{user_input}'")
        print("=" * 80)

        # Passo 1: Tokenização
        print("\n📝 PASSO 1: TOKENIZAÇÃO")
        print("-" * 40)
        tokens = self.tokenize(user_input)
        print(f"Tokens: {tokens}")

        # Passo 2: Identificação de entidades
        print("\n🏷️ PASSO 2: IDENTIFICAÇÃO DE ENTIDADES (NER)")
        print("-" * 40)
        entities = self.extract_entities(user_input)
        for entity_type, value in entities.items():
            print(f"  • {entity_type}: {value}")

        # Passo 3: Embedding e análise semântica
        print("\n🧠 PASSO 3: ANÁLISE SEMÂNTICA (EMBEDDINGS)")
        print("-" * 40)
        input_embedding = self.create_embedding(user_input)
        print(f"Embedding do input: {input_embedding}")

        # Passo 4: Cálculo de similaridade com tools
        print("\n📊 PASSO 4: MATCHING COM FERRAMENTAS")
        print("-" * 40)
        similarities = self.calculate_similarities(input_embedding)
        for tool, score in similarities.items():
            bar = "█" * int(score * 50)
            print(f"  {tool:15} [{bar:50}] {score:.2f}")

        # Passo 5: Decisão
        print("\n⚖️ PASSO 5: DECISÃO")
        print("-" * 40)
        best_tool, best_score = max(similarities.items(), key=lambda x: x[1])

        if best_score > 0.5:
            print(f"✅ USAR TOOL: {best_tool} (score: {best_score:.2f})")

            # Passo 6: Construção dos argumentos
            print("\n🔧 PASSO 6: CONSTRUÇÃO DOS ARGUMENTOS")
            print("-" * 40)
            arguments = self.build_arguments(best_tool, entities)
            print("Argumentos construídos:")
            print(json.dumps(arguments, indent=2))

            # Passo 7: Geração do tool_call
            print("\n📤 PASSO 7: GERAÇÃO DO TOOL_CALL")
            print("-" * 40)
            tool_call = {
                "tool_calls": [{
                    "type": "function",
                    "function": {
                        "name": best_tool,
                        "arguments": json.dumps(arguments)
                    }
                }]
            }
            print(json.dumps(tool_call, indent=2))
        else:
            print(f"❌ NÃO USAR TOOLS (melhor score: {best_score:.2f} < 0.5)")
            print("✅ GERAR RESPOSTA DIRETA")

        return similarities

    def tokenize(self, text: str) -> List[str]:
        """Simula tokenização"""
        # Simplificado - na realidade usa BPE ou SentencePiece
        import re
        tokens = re.findall(r'\w+|[^\w\s]', text.lower())
        return tokens

    def extract_entities(self, text: str) -> Dict[str, str]:
        """Simula extração de entidades"""
        entities = {}

        # Detectar CPF
        import re
        cpf_match = re.search(r'\b\d{11}\b', text)
        if cpf_match:
            entities["CPF"] = cpf_match.group()

        # Detectar data
        date_match = re.search(r'\d{2}/\d{2}/\d{4}', text)
        if date_match:
            entities["DATA_NASCIMENTO"] = date_match.group()

        # Detectar cidade
        cities = ["Natal", "São Paulo", "Rio de Janeiro", "Fortaleza"]
        for city in cities:
            if city.lower() in text.lower():
                entities["CIDADE"] = city
                break

        # Detectar ação
        if any(word in text.lower() for word in ["consultar", "verificar", "buscar"]):
            entities["AÇÃO"] = "consulta"
        elif any(word in text.lower() for word in ["oi", "olá", "bom dia"]):
            entities["AÇÃO"] = "saudação"

        return entities

    def create_embedding(self, text: str) -> List[float]:
        """Simula criação de embedding"""
        # Valores fictícios baseados em palavras-chave
        embedding = [0.0] * 5

        text_lower = text.lower()

        # Dimensão 0: Consulta/Dados
        if "consulta" in text_lower or "cpf" in text_lower:
            embedding[0] = 0.9
        if "contrato" in text_lower:
            embedding[2] = 0.8

        # Dimensão 1: Clima
        if "clima" in text_lower or "tempo" in text_lower:
            embedding[1] = 0.9

        # Dimensão 3: Matemática
        if "calcul" in text_lower or "soma" in text_lower:
            embedding[3] = 0.9

        # Dimensão 4: Saudação
        if "oi" in text_lower or "olá" in text_lower:
            embedding[4] = 0.1  # Baixo score para tools

        return embedding

    def calculate_similarities(self, input_embedding: List[float]) -> Dict[str, float]:
        """Calcula similaridade cosseno com cada tool"""
        similarities = {}

        for tool, tool_emb in self.tool_embeddings.items():
            # Similaridade cosseno simplificada
            dot_product = sum(a * b for a, b in zip(input_embedding, tool_emb))
            norm_input = sum(x**2 for x in input_embedding) ** 0.5
            norm_tool = sum(x**2 for x in tool_emb) ** 0.5

            if norm_input * norm_tool > 0:
                similarity = dot_product / (norm_input * norm_tool)
            else:
                similarity = 0

            similarities[tool] = max(0, similarity)  # Garantir não negativo

        return similarities

    def build_arguments(self, tool_name: str, entities: Dict[str, str]) -> Dict[str, str]:
        """Constrói argumentos para a tool selecionada"""
        if tool_name == "unimed_consult":
            args = {}
            if "CPF" in entities:
                args["cpf"] = entities["CPF"]
            if "DATA_NASCIMENTO" in entities:
                # Converter formato da data
                date = entities["DATA_NASCIMENTO"]
                parts = date.split("/")
                args["data_nascimento"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
            if "CIDADE" in entities:
                # Mapear cidade para formato da API
                args["cidade"] = f"{entities['CIDADE']}_Tasy"
            # Valores padrão
            args["tipo"] = "Contratos"
            args["protocolo"] = "0"
            return args

        return {}


def run_examples():
    """Executa exemplos demonstrativos"""
    simulator = LLMToolDecisionSimulator()

    # Exemplo 1: Saudação
    print("\n" + "=" * 80)
    print("EXEMPLO 1: SAUDAÇÃO SIMPLES")
    print("=" * 80)
    simulator.analyze_input("Oi, bom dia!")

    # Exemplo 2: Consulta Unimed
    print("\n\n" + "=" * 80)
    print("EXEMPLO 2: CONSULTA QUE PRECISA DE TOOL")
    print("=" * 80)
    simulator.analyze_input("Preciso consultar o contrato do CPF 00835690490, nascido em 28/03/1979 em Natal")

    # Exemplo 3: Pergunta genérica
    print("\n\n" + "=" * 80)
    print("EXEMPLO 3: PERGUNTA GENÉRICA")
    print("=" * 80)
    simulator.analyze_input("Qual a capital do Brasil?")

    # Resumo técnico
    print("\n\n" + "=" * 80)
    print("🔬 RESUMO TÉCNICO DO PROCESSO")
    print("=" * 80)
    print("""
    1. TOKENIZAÇÃO: Quebra o input em tokens processáveis
    2. NER: Identifica entidades (CPF, datas, cidades, etc.)
    3. EMBEDDING: Converte para vetor numérico de alta dimensão
    4. SIMILARIDADE: Compara com embeddings das ferramentas
    5. THRESHOLD: Se score > 0.5, usa tool; senão, resposta direta
    6. SLOT FILLING: Mapeia entidades para parâmetros da função
    7. SERIALIZAÇÃO: Gera JSON estruturado para tool_call

    🧠 O modelo real usa:
    - Transformers com ~100B+ parâmetros
    - Embeddings de ~4096+ dimensões
    - Attention mechanisms para contexto
    - Milhões de exemplos de treinamento
    - RLHF para refinamento
    """)


if __name__ == "__main__":
    run_examples()