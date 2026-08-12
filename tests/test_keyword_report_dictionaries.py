from aiporg.analyze_keyword_report.dictionaries import categorize_keyword


def test_categorize_keyword_maps_known_terms():
    assert categorize_keyword("청년AI인재") == "교육/고용"
    assert categorize_keyword("민생지원금") == "민생/복지"
