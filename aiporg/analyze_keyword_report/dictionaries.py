from __future__ import annotations


KEYWORD_CATEGORY_RULES: dict[str, str] = {
    "청년AI인재": "교육/고용",
    "민생지원금": "민생/복지",
    "역사문화관광": "문화/관광",
    "공주·부여관광": "문화/관광",
    "충청광역연합": "행정/권역",
    "농촌직불금": "민생/농업",
    "서해선·광역철도": "교통/인프라",
}

STOPWORDS: set[str] = {
    "충남",
    "충청남도",
    "박수현",
    "도정",
}


def categorize_keyword(term: str) -> str:
    return KEYWORD_CATEGORY_RULES.get(term, "기타")
