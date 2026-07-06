"""LLM 기반 배치 감성 분류.

사전 기반 분류의 '중립 편중'을 보완한다. 문서 다수를 한 번의 호출로
묶어 분류하여 무료 티어 rate-limit 안에서 동작하도록 설계.
배치 실패 시 해당 배치만 사전 기반으로 안전하게 fallback.
"""
from __future__ import annotations

import json
import logging
import re

from ..models import Sentiment
from ..analyze import sentiment as lex

log = logging.getLogger(__name__)

_LABELS = {"긍정": Sentiment.POSITIVE, "부정": Sentiment.NEGATIVE,
           "중립": Sentiment.NEUTRAL, "혼재": Sentiment.MIXED}


def _redact(msg: str) -> str:
    """로그/예외 문자열에서 API 키(?key=... , Bearer ...) 마스킹."""
    msg = re.sub(r"key=[\w.\-]+", "key=***", msg)
    msg = re.sub(r"(Bearer\s+)[\w.\-]+", r"\1***", msg)
    return msg

_SYSTEM = (
    "너는 한국어 온라인 여론 감성 분류기다. 각 문장의 감성을 "
    "긍정/부정/중립/혼재 중 하나로만 분류한다. 공공기관·정치인·정책에 대한 "
    "지지·기대·성과는 긍정, 비판·우려·논란·갈등은 부정, 단순 사실 전달은 중립, "
    "긍·부정이 함께면 혼재로 판단한다."
)


def _prompt(batch: list[str]) -> str:
    lines = "\n".join(f"{i+1}. {t[:200]}" for i, t in enumerate(batch))
    return (
        "다음 문장들의 감성을 분류하라. 반드시 입력 순서대로, 각 항목당 "
        "'긍정'|'부정'|'중립'|'혼재' 중 하나만 담은 JSON 배열로만 답하라.\n"
        f"항목 수는 정확히 {len(batch)}개여야 한다.\n\n{lines}"
    )


def _parse(text: str, n: int) -> list[Sentiment] | None:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None
    if len(arr) != n:
        return None
    out = []
    for v in arr:
        out.append(_LABELS.get(str(v).strip(), Sentiment.NEUTRAL))
    return out


def classify_batch(client, texts: list[str], batch_size: int = 40,
                   max_docs: int = 1000, pace_sec: float = 4.0) -> list[Sentiment]:
    """texts 를 배치로 LLM 분류. 무료 티어 rate-limit 대비 배치 간 간격 + 1회 재시도.
    실패 배치는 사전 기반으로 대체."""
    import time

    results: list[Sentiment] = []
    capped = texts[:max_docs]
    n_batches = (len(capped) + batch_size - 1) // batch_size
    for idx, bi in enumerate(range(0, len(capped), batch_size)):
        batch = capped[bi:bi + batch_size]
        got = None
        for attempt in range(2):
            try:
                raw = client.generate(_SYSTEM, _prompt(batch), temperature=0.0)
                got = _parse(raw, len(batch))
                if got is not None:
                    break
            except Exception as e:  # noqa: BLE001
                if attempt == 0:
                    time.sleep(pace_sec * 2)   # 429 등 -> 백오프 후 1회 재시도
                    continue
                log.warning("LLM 감성 배치 실패(%d/%d), 사전 fallback: %s",
                            idx + 1, n_batches, _redact(str(e)))
        if got is None:
            got = [lex.classify(t) for t in batch]
        results.extend(got)
        log.info("감성 배치 %d/%d 완료", idx + 1, n_batches)
        if idx < n_batches - 1:
            time.sleep(pace_sec)               # RPM 완화
    if len(texts) > len(capped):
        results.extend(lex.classify(t) for t in texts[len(capped):])
    return results
