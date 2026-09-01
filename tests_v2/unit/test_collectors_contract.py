import asyncio
import inspect

from app.collectors.base import BaseCollector
from app.collectors.errors import CollectionError, CollectorError
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


class StubCollector(BaseCollector):
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        return []

    async def fetch(self, result: SearchResult) -> RawDocument:
        raise NotImplementedError


def test_base_collector_declares_async_search_and_fetch_contracts() -> None:
    assert inspect.isabstract(BaseCollector)

    search = BaseCollector.search
    fetch = BaseCollector.fetch
    assert inspect.iscoroutinefunction(search)
    assert inspect.iscoroutinefunction(fetch)
    assert inspect.signature(search).return_annotation == list[SearchResult]
    assert inspect.signature(fetch).return_annotation == RawDocument


def test_concrete_collector_can_implement_contract_without_storage_dependencies() -> None:
    collector = StubCollector()
    query = SearchQuery(query="박수현", channels=[])

    assert asyncio.run(collector.search(query)) == []


def test_collector_error_preserves_structured_context() -> None:
    error = CollectorError(
        code="timeout",
        message="provider timed out",
        retryable=True,
        details={"timeout_seconds": 10},
    )

    assert str(error) == "provider timed out"
    assert error.code == "timeout"
    assert error.retryable is True
    assert error.details == {"timeout_seconds": 10}


def test_collection_error_contains_collector_errors_and_partial_status() -> None:
    cause = CollectorError(code="http_error", message="upstream failed")
    error = CollectionError(
        message="collection completed with errors",
        errors=[cause],
        partial=True,
    )

    assert str(error) == "collection completed with errors"
    assert error.errors == (cause,)
    assert error.partial is True


def test_collector_contract_has_no_database_or_llm_dependency() -> None:
    module_names = set(inspect.getmodule(BaseCollector).__dict__)

    assert not any(
        name.startswith(("sqlalchemy", "app.models", "app.repositories", "app.llm"))
        for name in module_names
    )
