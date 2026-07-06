"""실 LLM provider 구현 (Gemini 2.5 Pro / OpenAI GPT-5).

API 키가 없으면 생성 시점에 예외를 던지므로, 기본 실행은 template provider
를 사용한다. grounded 프롬프트(prompts.py)를 그대로 주입한다.
"""
from __future__ import annotations

import os

from .base import LLMClient


class GeminiClient(LLMClient):
    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model = model
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다")

    def generate(self, system: str, prompt: str, temperature: float = 0.2) -> str:
        import requests

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-5"):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 필요합니다")

    def generate(self, system: str, prompt: str, temperature: float = 0.2) -> str:
        import requests

        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model, "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
