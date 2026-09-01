"""Collector Engine contracts for AIPORG 2.0."""

from app.collectors.base import BaseCollector
from app.collectors.daum_news import DaumNewsCollector
from app.collectors.errors import CollectionError, CollectorError
from app.collectors.naver_news import NaverNewsCollector
from app.collectors.transport import HttpResponse, RequestsTransport

__all__ = [
    "BaseCollector",
    "DaumNewsCollector",
    "CollectionError",
    "CollectorError",
    "HttpResponse",
    "NaverNewsCollector",
    "RequestsTransport",
]
