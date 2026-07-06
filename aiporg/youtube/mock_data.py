"""테스트/시연용 Mock ApiClient (YOUTUBE_API_KEY 없이 파이프라인 검증).

실제 2026년 6월 충남/박수현 유튜브 상황을 모사한 결정론적 데이터.
"""
from __future__ import annotations

from . import config as C

_VIDEOS: list[dict] = [
    {"id": "vid001", "title": "박수현 충남도지사 취임…'통하는 충남' 비전 발표",
     "desc": "박수현 충남도지사가 민선9기 도정 비전을 발표했다. 소통과 민생을 강조.",
     "channel": "충남도정뉴스", "views": 152000, "likes": 3200, "comments": 480, "topic": "행정"},
    {"id": "vid002", "title": "충남 아산 AI데이터센터 2조 투자 유치 성과",
     "desc": "충청남도가 아산에 대규모 AI데이터센터 투자를 유치했다. 반도체 산업 기대.",
     "channel": "경제TV", "views": 98000, "likes": 2100, "comments": 210, "topic": "산업"},
    {"id": "vid003", "title": "박수현 지사 야간경제 정책 현장 점검",
     "desc": "부여 서동연꽃축제에서 야간경제 활성화 방안을 점검하는 박수현 도지사.",
     "channel": "관광충남", "views": 45000, "likes": 900, "comments": 88, "topic": "관광"},
    {"id": "vid004", "title": "충남 화력발전 탈석탄 논란…주민 반발",
     "desc": "충남 화력발전 폐지와 탈석탄 정책을 두고 지역 주민 반발과 우려가 나온다.",
     "channel": "환경뉴스", "views": 67000, "likes": 400, "comments": 320, "topic": "환경"},
    {"id": "vid005", "title": "충남도의회 제13대 개원…전반기 원구성 완료",
     "desc": "충남도의회가 제13대 전반기 원구성을 마치고 개원식을 열었다.",
     "channel": "의회방송", "views": 23000, "likes": 300, "comments": 40, "topic": "행정"},
    {"id": "vid006", "title": "충남 소상공인 지원 확대…민선9기 복지정책",
     "desc": "충청남도가 소상공인과 취약계층 돌봄 지원을 확대한다고 밝혔다.",
     "channel": "복지충남", "views": 31000, "likes": 620, "comments": 55, "topic": "복지"},
    {"id": "vid007", "title": "천안 반도체 패키징 증설…일자리 기대",
     "desc": "삼성전자 천안 반도체 패키징 라인 증설로 지역 일자리 창출 기대.",
     "channel": "산업뉴스", "views": 88000, "likes": 1800, "comments": 130, "topic": "산업"},
    {"id": "vid008", "title": "충남 전력인프라 부족 우려…투자 발목",
     "desc": "데이터센터 유치에도 전력인프라 부족으로 우려의 목소리가 커진다.",
     "channel": "이슈충남", "views": 52000, "likes": 350, "comments": 190, "topic": "산업"},
    {"id": "vid009", "title": "박수현 충남도지사 첫 인선 발표…정무부지사 임명",
     "desc": "박수현 도지사가 정무부지사 등 첫 인선을 발표했다.",
     "channel": "충남도정뉴스", "views": 41000, "likes": 500, "comments": 96, "topic": "행정"},
    {"id": "vid010", "title": "충남 관광 활성화…해양레저 콘텐츠 확대",
     "desc": "충청남도가 서해안 해양레저 관광 콘텐츠를 확대한다.",
     "channel": "관광충남", "views": 19000, "likes": 280, "comments": 22, "topic": "관광"},
    {"id": "vid011", "title": "통하는 충남 홍보영상", "desc": "민선9기 통하는 충남 슬로건 홍보.",
     "channel": "충남도청", "views": 12000, "likes": 150, "comments": 8, "topic": "행정"},
    {"id": "vid012", "title": "충남 교통 국도 병목 개선 사업 추진",
     "desc": "도내 국도 위험·병목 구간 개선 사업을 추진한다.",
     "channel": "교통뉴스", "views": 8000, "likes": 90, "comments": 3, "topic": "교통"},
]

_POS_C = ["기대됩니다 응원합니다", "정책 방향 좋네요", "잘 추진되길 바랍니다",
          "충남 발전 기대돼요", "소통하는 모습 보기 좋습니다"]
_NEG_C = ["전력부족 우려됩니다", "혈세 낭비 아닌가요", "탁상행정 같네요",
          "주민 의견 반영이 부족합니다", "실망스럽습니다"]
_NEU_C = ["관련 뉴스 잘 봤습니다", "정보 감사합니다", "자세한 설명 부탁드려요"]


class MockApiClient:
    """ApiClient Protocol 구현 (결정론적 Mock)."""

    def search(self, keyword: str, cfg: "C.YouTubeConfig") -> list[str]:
        # 키워드별로 일부 영상 반환(중복 포함 → dedup 검증)
        hits = [v["id"] for v in _VIDEOS
                if keyword in v["title"] or keyword in v["desc"]
                or keyword in ("충남", "충청남도")]
        return hits[:C.VIDEOS_PER_KEYWORD]

    def videos(self, video_ids: list[str]) -> list[dict]:
        out = []
        for vid in video_ids:
            v = next((x for x in _VIDEOS if x["id"] == vid), None)
            if not v:
                continue
            out.append({
                "id": vid,
                "snippet": {"title": v["title"], "description": v["desc"],
                            "channelTitle": v["channel"],
                            "publishedAt": "2026-06-15T09:00:00Z"},
                "statistics": {"viewCount": str(v["views"]), "likeCount": str(v["likes"]),
                               "commentCount": str(v["comments"])},
            })
        return out

    def comment_threads(self, video_id: str, max_results: int) -> list[dict]:
        v = next((x for x in _VIDEOS if x["id"] == video_id), None)
        if not v:
            return []
        # 토픽 성향에 따라 감성 혼합
        if v["topic"] == "환경" or "전력" in v["title"]:
            pool = _NEG_C * 3 + _NEU_C + _POS_C
        elif v["topic"] in ("산업", "관광", "복지"):
            pool = _POS_C * 3 + _NEU_C + _NEG_C
        else:
            pool = _POS_C + _NEG_C + _NEU_C * 2
        items = []
        for i, text in enumerate(pool[:max_results]):
            items.append({
                "id": f"{video_id}_c{i}",
                "snippet": {"topLevelComment": {"id": f"{video_id}_c{i}", "snippet": {
                    "textDisplay": text, "likeCount": (len(pool) - i) * 3,
                    "authorDisplayName": f"user_{i}",
                    "publishedAt": "2026-06-16T10:00:00Z"}}},
            })
        return items


def mock_config() -> "C.YouTubeConfig":
    import tempfile
    import os
    db = os.path.join(tempfile.gettempdir(), "youtube_mock.db")
    return C.YouTubeConfig(db_path=db)
