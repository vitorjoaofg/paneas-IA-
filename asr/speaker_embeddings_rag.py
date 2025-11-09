"""
RAG-based Speaker Pattern Recognition System.
Uses semantic embeddings to classify segments based on similarity to known patterns.
"""

import logging
import json
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)

# Typical patterns for each speaker role (PT-BR call center context)
ATTENDANT_EXAMPLES = [
    "Meu nome é Carlos, sou da Claro",
    "Posso confirmar seus dados pessoais?",
    "Vou precisar do seu CPF para continuar",
    "Temos uma oferta especial para você hoje",
    "Estamos com um plano de R$ 39,90 por mês",
    "Vamos fazer sua migração aqui hoje",
    "Preciso confirmar seu endereço completo",
    "Você autoriza a gravação desta ligação?",
    "Vou começar a fazer seu cadastro agora",
    "Lembrando que o vencimento é dia 10",
    "Você pode mudar a data no aplicativo depois",
    "Posso prosseguir com a ativação?",
    "Vou encaminhar sua solicitação para o setor responsável",
    "Obrigado por entrar em contato com a nossa empresa",
    "O protocolo do seu atendimento é",
    "Compareça em uma de nossas lojas com sua documentação",
    "Aguarde um momento enquanto consulto no sistema",
    "Qual é o seu nome completo?",
    "Qual é o seu CPF?",
    "Me confirma seu telefone de contato?",
    "Você tem e-mail cadastrado?",
    "Qual seria o melhor dia para o pagamento?",
    "Posso oferecer um desconto especial",
    "Nós da empresa estamos entrando em contato",
    "Esse é o melhor plano para o seu perfil",
    "Vou te passar para o supervisor",
    "Podemos agendar uma visita técnica",
    "Você já recebeu a fatura por e-mail?",
    "Esse valor já inclui todos os tributos",
    "A instalação é totalmente gratuita",
]

CLIENT_EXAMPLES = [
    "Sim",
    "Não",
    "Ok",
    "Tá bom",
    "Pode ser",
    "Vamos",
    "Entendi",
    "Isso mesmo",
    "Esse mesmo",
    "Tá certo",
    "Perfeito",
    "Beleza",
    "Ah tá",
    "Claro",
    "Com certeza",
    "Uhm",
    "Aham",
    "Obrigado",
    "Obrigada",
    "Oi",
    "Alô",
    "Estou no nome da minha mãe",
    "Queria passar para o meu nome",
    "Quanto custa?",
    "E se eu não pagar?",
    "Posso cancelar depois?",
    "Não tenho interesse",
    "Não quero agora",
    "Vou pensar",
    "Depois eu ligo de volta",
    "Não é comigo que você quer falar",
    "Tá, mas eu não pedi isso",
    "Vocês ligam todo dia",
    "Já disse que não quero",
    "Tira meu número da lista",
    "Como eu cancelo?",
    "Meu telefone é",
    "Meu CPF é",
    "Meu endereço é",
]


class SpeakerEmbeddingsRAG:
    """RAG system for speaker classification using semantic similarity."""

    def __init__(self, cache_dir: str = "/cache/speaker_embeddings"):
        """
        Initialize the RAG system.

        Args:
            cache_dir: Directory to cache embeddings
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.attendant_embeddings = None
        self.client_embeddings = None
        self.embedding_dim = 384  # sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

        # Try to load cached embeddings
        self._load_or_create_embeddings()

    def _load_or_create_embeddings(self):
        """Load embeddings from cache or create them."""
        cache_file = self.cache_dir / "speaker_pattern_embeddings.pkl"

        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.attendant_embeddings = data['attendant']
                    self.client_embeddings = data['client']
                    self.embedding_dim = data['dim']
                logger.info(f"Loaded cached speaker embeddings from {cache_file}")
                return
            except Exception as e:
                logger.warning(f"Failed to load cached embeddings: {e}")

        # Create embeddings using simple TF-IDF-like approach (no external dependencies)
        logger.info("Creating speaker pattern embeddings...")
        self._create_simple_embeddings()

        # Cache the embeddings
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'attendant': self.attendant_embeddings,
                    'client': self.client_embeddings,
                    'dim': self.embedding_dim
                }, f)
            logger.info(f"Cached speaker embeddings to {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to cache embeddings: {e}")

    def _create_simple_embeddings(self):
        """Create simple character n-gram based embeddings (no external model needed)."""
        from collections import Counter

        def text_to_ngrams(text: str, n: int = 3) -> List[str]:
            """Convert text to character n-grams."""
            text = text.lower()
            return [text[i:i+n] for i in range(len(text) - n + 1)]

        def text_to_embedding(text: str, vocab: Dict[str, int], dim: int) -> np.ndarray:
            """Convert text to embedding vector using n-gram frequencies."""
            ngrams = text_to_ngrams(text)
            counts = Counter(ngrams)
            embedding = np.zeros(dim)

            for ngram, count in counts.items():
                if ngram in vocab:
                    embedding[vocab[ngram]] = count

            # L2 normalization
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding

        # Build vocabulary from all examples
        all_texts = ATTENDANT_EXAMPLES + CLIENT_EXAMPLES
        all_ngrams = []
        for text in all_texts:
            all_ngrams.extend(text_to_ngrams(text))

        ngram_counts = Counter(all_ngrams)
        # Keep top N most frequent n-grams as vocabulary
        top_ngrams = [ng for ng, _ in ngram_counts.most_common(self.embedding_dim)]
        vocab = {ng: i for i, ng in enumerate(top_ngrams)}

        # Create embeddings for each example
        self.attendant_embeddings = np.array([
            text_to_embedding(text, vocab, self.embedding_dim)
            for text in ATTENDANT_EXAMPLES
        ])

        self.client_embeddings = np.array([
            text_to_embedding(text, vocab, self.embedding_dim)
            for text in CLIENT_EXAMPLES
        ])

        # Store vocab for query embedding
        self.vocab = vocab

    def _embed_text(self, text: str) -> np.ndarray:
        """Embed a single text using the same method as training examples."""
        from collections import Counter

        def text_to_ngrams(text: str, n: int = 3) -> List[str]:
            text = text.lower()
            return [text[i:i+n] for i in range(len(text) - n + 1)]

        ngrams = text_to_ngrams(text)
        counts = Counter(ngrams)
        embedding = np.zeros(self.embedding_dim)

        for ngram, count in counts.items():
            if ngram in self.vocab:
                embedding[self.vocab[ngram]] = count

        # L2 normalization
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def classify_segment(
        self,
        text: str,
        top_k: int = 5
    ) -> Tuple[str, float, List[Tuple[str, str, float]]]:
        """
        Classify a segment based on semantic similarity to known patterns.

        Args:
            text: The segment text to classify
            top_k: Number of similar examples to retrieve

        Returns:
            Tuple of (predicted_role, confidence, top_similar_examples)
            - predicted_role: "Atendente" or "Cliente"
            - confidence: 0.0 to 1.0
            - top_similar_examples: List of (role, example_text, similarity_score)
        """
        if not text or not text.strip():
            return "Cliente", 0.0, []

        # Embed the query text
        query_embedding = self._embed_text(text)

        # Compute similarity to all examples
        attendant_similarities = np.dot(self.attendant_embeddings, query_embedding)
        client_similarities = np.dot(self.client_embeddings, query_embedding)

        # Get top-k from each role
        top_attendant_idx = np.argsort(attendant_similarities)[-top_k:][::-1]
        top_client_idx = np.argsort(client_similarities)[-top_k:][::-1]

        # Combine and sort by similarity
        similar_examples = []

        for idx in top_attendant_idx:
            similar_examples.append((
                "Atendente",
                ATTENDANT_EXAMPLES[idx],
                float(attendant_similarities[idx])
            ))

        for idx in top_client_idx:
            similar_examples.append((
                "Cliente",
                CLIENT_EXAMPLES[idx],
                float(client_similarities[idx])
            ))

        # Sort by similarity
        similar_examples.sort(key=lambda x: x[2], reverse=True)
        top_examples = similar_examples[:top_k]

        # Vote based on top examples
        attendant_score = sum(sim for role, _, sim in top_examples if role == "Atendente")
        client_score = sum(sim for role, _, sim in top_examples if role == "Cliente")

        # Predict role
        if attendant_score > client_score:
            predicted_role = "Atendente"
            confidence = attendant_score / (attendant_score + client_score) if (attendant_score + client_score) > 0 else 0.0
        else:
            predicted_role = "Cliente"
            confidence = client_score / (attendant_score + client_score) if (attendant_score + client_score) > 0 else 0.0

        return predicted_role, confidence, top_examples

    def bulk_classify(
        self,
        segments: List[Dict[str, Any]],
        confidence_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Classify multiple segments using RAG.

        Args:
            segments: List of segments with 'text' field
            confidence_threshold: Minimum confidence to override existing label

        Returns:
            List of segments with 'rag_speaker', 'rag_confidence', and 'rag_examples' fields
        """
        results = []

        for seg in segments:
            text = seg.get("text", "").strip()

            if not text:
                results.append({
                    **seg,
                    "rag_speaker": None,
                    "rag_confidence": 0.0,
                    "rag_examples": []
                })
                continue

            predicted_role, confidence, examples = self.classify_segment(text, top_k=3)

            results.append({
                **seg,
                "rag_speaker": predicted_role,
                "rag_confidence": confidence,
                "rag_examples": examples
            })

        return results


def enhance_segments_with_rag(
    segments: List[Dict[str, Any]],
    confidence_threshold: float = 0.65
) -> List[Dict[str, Any]]:
    """
    Enhance segment speaker labels using RAG predictions.

    Args:
        segments: List of segments with 'speaker' and 'text' fields
        confidence_threshold: Minimum RAG confidence to override existing label

    Returns:
        Enhanced segments with potentially corrected speaker labels
    """
    try:
        rag = SpeakerEmbeddingsRAG()
        rag_results = rag.bulk_classify(segments)

        corrections_made = 0

        for i, seg in enumerate(rag_results):
            original_speaker = seg.get("speaker")
            rag_speaker = seg.get("rag_speaker")
            rag_confidence = seg.get("rag_confidence", 0.0)

            # Override if RAG has high confidence and disagrees
            if (rag_speaker and
                rag_confidence >= confidence_threshold and
                original_speaker != rag_speaker):

                logger.debug(
                    f"RAG correction: '{seg.get('text', '')[:50]}...' "
                    f"{original_speaker} -> {rag_speaker} "
                    f"(confidence: {rag_confidence:.2f})"
                )
                seg["speaker"] = rag_speaker
                corrections_made += 1

        logger.info(f"RAG enhanced {len(segments)} segments, made {corrections_made} corrections")
        return rag_results

    except Exception as e:
        logger.error(f"RAG enhancement failed: {e}", exc_info=True)
        return segments
