"""Region synonyms and query-bias vocabulary applied in code, not by the LLM."""

REGION_ALIASES = {"충청남도": ["충청남도", "충남"]}

# Tokens that pre-judge direction; allowed only in FRAME_DISCOVERY queries.
BIAS_TERMS = frozenset(
    {"효과", "창출", "기대", "호재", "활성화", "논란", "우려", "문제", "과제", "한계", "반발"}
)
