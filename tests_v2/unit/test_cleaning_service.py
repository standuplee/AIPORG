from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.cleaning.service import CleaningService
from app.core.enums import ChannelType
from app.schemas.document import RawDocument


def document(*, url: str = "https://NEWS.example.test/article?b=2&utm_source=x&a=1#comments") -> RawDocument:
    return RawDocument(
        document_id=uuid4(),
        source="test",
        channel=ChannelType.NEWS,
        platform="test",
        title="  충남\u00a0   AI  \n 뉴스 ",
        url=url,
        published_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        query="박수현",
        body="첫\u00a0 문장\n\n <b>둘째</b>  문장",
        metadata={},
        collected_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )


def test_cleaning_normalizes_text_and_canonicalizes_url() -> None:
    source = document()
    cleaned = CleaningService().clean(source)

    assert cleaned.title == "충남 AI 뉴스"
    assert cleaned.body == "첫 문장 둘째 문장"
    assert cleaned.canonical_url == "https://news.example.test/article?b=2&a=1"
    assert cleaned.document_id == source.document_id


def test_cleaning_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http or https"):
        CleaningService().clean(document(url="ftp://example.test/article"))


def test_cleaning_rejects_empty_body() -> None:
    empty = document()
    empty = empty.model_copy(update={"body": " \n\t "})

    with pytest.raises(ValueError, match="body"):
        CleaningService().clean(empty)
