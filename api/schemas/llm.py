from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = Field(default="paneas-q32b")
    messages: List[ChatMessage]
    max_tokens: int = Field(default=1024, ge=1, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    quality_priority: bool = False
    provider: Literal["paneas", "openai"] = Field(default="paneas")


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
