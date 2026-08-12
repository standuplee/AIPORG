from datetime import date

from aiporg.collect.news import DaumNewsCollector


def test_daum_news_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    docs = DaumNewsCollector().collect(["박수현"], date(2026, 7, 1), date(2026, 7, 31))

    assert docs == []


def test_daum_news_uses_kakao_web_search_and_filters_domains(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "documents": [
                    {
                        "title": "<b>박수현</b> 충남 AI",
                        "contents": "충남 AI 기사 요약",
                        "url": "https://news.daum.net/politics/123",
                        "datetime": "2026-07-10T09:00:00.000+09:00",
                    },
                    {
                        "title": "다음 뷰 링크",
                        "contents": "다음 계열 뷰 링크",
                        "url": "https://v.daum.net/v/20260710090000123",
                        "datetime": "2026-07-10T09:00:00.000+09:00",
                    },
                    {
                        "title": "제외 대상",
                        "contents": "example.com 은 제외",
                        "url": "https://example.com/post",
                        "datetime": "2026-07-10T09:00:00.000+09:00",
                    },
                ],
                "meta": {"is_end": True},
            }

    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers, timeout))
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    docs = DaumNewsCollector().collect(["박수현"], date(2026, 7, 1), date(2026, 7, 31))

    assert len(docs) == 2
    assert all("daum.net" in doc.url for doc in docs)
    assert calls[0][0] == "https://dapi.kakao.com/v2/search/web"
    assert calls[0][2]["Authorization"] == "KakaoAK test-key"
