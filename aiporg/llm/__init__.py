"""LLM 서술 계층.

공공기관 문체 생성을 담당한다. provider 는 3종:
  - template : API 키 없이 동작하는 결정론적 문장 생성기 (재현성 보장, 기본값)
  - gemini   : Gemini 2.5 Pro
  - openai   : GPT-5
Narrator 가 provider 를 추상화하여 보고서 각 절의 서술문을 반환한다.
"""
from .narrator import Narrator, build_narrator

__all__ = ["Narrator", "build_narrator"]
