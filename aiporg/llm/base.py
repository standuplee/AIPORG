"""LLM 클라이언트 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """텍스트 생성 계약. 모든 provider 는 grounded 프롬프트를 받아 문장을 반환."""

    @abstractmethod
    def generate(self, system: str, prompt: str, temperature: float = 0.2) -> str:
        ...
