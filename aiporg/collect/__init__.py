"""수집 계층.

BaseCollector 인터페이스와 채널별 수집기, 그리고 이들을 실행하는
CollectorRegistry 를 제공한다. 라이브 수집이 불가능한 환경(네트워크/인증
부재)에서는 각 수집기가 빈 결과로 정상 degrade 하며, 파이프라인은
fixture 데이터로 대체 실행된다.
"""
from .base import BaseCollector, CollectorRegistry, build_registry

__all__ = ["BaseCollector", "CollectorRegistry", "build_registry"]
