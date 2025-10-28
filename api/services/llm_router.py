from enum import Enum

from pydantic import BaseModel


class LLMTarget(str, Enum):
    FP16 = "fp16"
    INT4 = "int4"
    OPENAI = "openai"


class LLMRoutingDecision(BaseModel):
    target: LLMTarget
    reason: str


class LLMRouter:
    THRESHOLD_SHORT_PROMPT = 512
    THRESHOLD_LONG_CONTEXT = 32768  # Limite máximo do Qwen2.5 INT4 (32k tokens)
    MAX_CONTEXT_LENGTH = 32768  # Hard limit - acima disso retorna erro

    def __init__(self, strategy: str = "auto"):
        self.strategy = strategy

    def route(
        self,
        prompt_tokens: int,
        context_length: int,
        quality_priority: bool = False,
    ) -> LLMRoutingDecision:
        if self.strategy == LLMTarget.FP16.value:
            return LLMRoutingDecision(target=LLMTarget.FP16, reason="forced_fp16")

        if self.strategy == LLMTarget.INT4.value:
            return LLMRoutingDecision(target=LLMTarget.INT4, reason="forced_int4")

        if quality_priority:
            return LLMRoutingDecision(target=LLMTarget.FP16, reason="quality_priority")

        # Removido fallback para FP16 em long context - INT4 aguenta até 32k
        # Se passar de 32k, será tratado como erro no endpoint

        if prompt_tokens < self.THRESHOLD_SHORT_PROMPT:
            return LLMRoutingDecision(target=LLMTarget.INT4, reason="short_prompt_latency")

        return LLMRoutingDecision(target=LLMTarget.INT4, reason="default_throughput")
