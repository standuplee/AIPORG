from datetime import date, datetime, timezone

from app.search.quant import MIN_TREND_POSTS, build_quantitative, volume_lines


class P:
    def __init__(self, channel, at):
        self.channel, self.published_at = channel, at


def _at(day, hour=3):
    return datetime(2026, 8, day, hour, tzinfo=timezone.utc)


def test_counts_come_only_from_posts_and_are_split_by_channel_week_and_day():
    posts = [P("BLOG", _at(3)), P("BLOG", _at(4)), P("CAFE", _at(11)), P("BLOG", _at(11)), P("CAFE", _at(25)),
             P("BLOG", None), P("BLOG", datetime(2026, 7, 20, tzinfo=timezone.utc))]
    q = build_quantitative(posts, date(2026, 8, 1), date(2026, 8, 31))
    assert (q.total_posts, q.dated_posts, q.undated_posts, q.out_of_period_posts) == (7, 5, 1, 1)
    assert q.by_channel == {"BLOG": 5, "CAFE": 2}
    assert q.weekly["2026-08-03"] == 2 and q.weekly["2026-08-10"] == 2 and q.weekly["2026-08-24"] == 1
    assert sum(q.weekly.values()) == sum(q.daily.values()) == q.dated_posts      # nothing is added or lost
    assert q.daily["2026-08-03"] == 1 and q.daily["2026-08-02"] == 0               # zeros fill the period
    assert q.weekly_by_channel["CAFE"]["2026-08-10"] == 1


def test_kst_date_is_used_so_a_late_utc_post_lands_on_the_next_day():
    q = build_quantitative([P("BLOG", datetime(2026, 8, 3, 16, tzinfo=timezone.utc))], date(2026, 8, 1), date(2026, 8, 31))
    assert q.daily["2026-08-04"] == 1 and q.daily["2026-08-03"] == 0


def test_few_dated_posts_give_counts_but_no_trend_sentence():
    q = build_quantitative([P("BLOG", None) for _ in range(6)] + [P("BLOG", _at(5))], date(2026, 8, 1), date(2026, 8, 31))
    text = "\n".join(volume_lines(q))
    assert "7건" in text and "게시일 확인 1건" in text and "추이는 산출하지 않았다" in text and "주별 게시 건수" not in text
    assert q.dated_posts < MIN_TREND_POSTS


def test_trend_sentences_name_the_peak_week_without_inventing_numbers():
    posts = [P("BLOG", _at(d)) for d in (3, 4, 5, 6, 12)]
    lines = volume_lines(build_quantitative(posts, date(2026, 8, 1), date(2026, 8, 31)))
    assert any("08-03 4건" in l and "08-10 1건" in l for l in lines) and any(l == "가장 많은 주: 08-03주 4건" for l in lines)
