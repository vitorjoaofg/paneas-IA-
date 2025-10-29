from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    """Definição de uma função que pode ser chamada pelo LLM"""
    name: str
    description: str
    parameters: Dict[str, Any]


class Tool(BaseModel):
    """Tool disponível para o LLM"""
    type: Literal["function"]
    function: ToolFunction


class FunctionCall(BaseModel):
    """Chamada de função realizada pelo LLM"""
    name: str
    arguments: str  # JSON string com os argumentos


class ToolCall(BaseModel):
    """Tool call realizada pelo assistente"""
    id: str
    type: Literal["function"]
    function: FunctionCall


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None  # Para mensagens do assistant
    tool_call_id: Optional[str] = None  # Para mensagens de role=tool
    name: Optional[str] = None  # Nome da função para role=tool


class ChatRequest(BaseModel):
    model: str = Field(default="paneas-q32b")
    messages: List[ChatMessage]
    max_tokens: int = Field(default=1024, ge=1, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    quality_priority: bool = False
    provider: Literal["paneas", "openai"] = Field(default="paneas")
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[Literal["none", "auto", "required"], Dict[str, Any]]] = Field(default="auto")


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class UsageMetrics(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    model: str
    choices: List[ChatChoice]
    usage: UsageMetrics
