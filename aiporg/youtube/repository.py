"""SQLite Repository (youtube_videos / youtube_comments /
youtube_analysis_summary / youtube_cache)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .schema import Comment, Video

SCHEMA: str = """
CREATE TABLE IF NOT EXISTS youtube_videos (
    video_id     TEXT PRIMARY KEY,
    title        TEXT,
    description  TEXT,
    channel_title TEXT,
    published_at TEXT,
    view_count   INTEGER DEFAULT 0,
    like_count   INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    url          TEXT,
    matched_keywords TEXT,
    sentiment    TEXT,
    topic        TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS youtube_comments (
    comment_id   TEXT PRIMARY KEY,
    video_id     TEXT,
    text         TEXT,
    published_at TEXT,
    like_count   INTEGER DEFAULT 0,
    author_hash  TEXT,
    sentiment    TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS youtube_analysis_summary (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT,
    period_end   TEXT,
    report_json  TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS youtube_cache (
    cache_key    TEXT PRIMARY KEY,
    payload      TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_comments_video ON youtube_comments(video_id);
"""


class YouTubeRepository:
    """수집 데이터 영속화 및 조회."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    # -- videos ----------------------------------------------------------- #
    def save_videos(self, videos: list[Video]) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                """INSERT INTO youtube_videos
                   (video_id,title,description,channel_title,published_at,view_count,
                    like_count,comment_count,url,matched_keywords,sentiment,topic)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(video_id) DO UPDATE SET
                     view_count=excluded.view_count, like_count=excluded.like_count,
                     comment_count=excluded.comment_count, sentiment=excluded.sentiment,
                     topic=excluded.topic""",
                [(v.video_id, v.title, v.description, v.channel_title, v.published_at,
                  v.view_count, v.like_count, v.comment_count, v.url,
                  json.dumps(v.matched_keywords, ensure_ascii=False), v.sentiment, v.topic)
                 for v in videos],
            )
            conn.commit()

    def save_comments(self, comments: list[Comment]) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                """INSERT INTO youtube_comments
                   (comment_id,video_id,text,published_at,like_count,author_hash,sentiment)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(comment_id) DO UPDATE SET
                     like_count=excluded.like_count, sentiment=excluded.sentiment""",
                [(c.comment_id, c.video_id, c.text, c.published_at, c.like_count,
                  c.author_hash, c.sentiment) for c in comments],
            )
            conn.commit()

    def save_report(self, period_start: str, period_end: str, report_json: str) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO youtube_analysis_summary (period_start,period_end,report_json)"
                " VALUES (?,?,?)", (period_start, period_end, report_json))
            conn.commit()

    # -- cache ------------------------------------------------------------ #
    def cache_get(self, key: str, ttl_days: int) -> Optional[dict]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT payload, created_at FROM youtube_cache WHERE cache_key=?",
                (key,)).fetchone()
        if not row:
            return None
        try:
            created = datetime.fromisoformat(row[1])
        except Exception:
            return None
        if datetime.now() - created > timedelta(days=ttl_days):
            return None
        return json.loads(row[0])

    def cache_put(self, key: str, payload: dict) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO youtube_cache (cache_key,payload,created_at) VALUES (?,?,?)"
                " ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,"
                " created_at=excluded.created_at",
                (key, json.dumps(payload, ensure_ascii=False),
                 datetime.now().isoformat()))
            conn.commit()

    def counts(self) -> dict[str, int]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            v = conn.execute("SELECT COUNT(*) FROM youtube_videos").fetchone()[0]
            c = conn.execute("SELECT COUNT(*) FROM youtube_comments").fetchone()[0]
        return {"videos": v, "comments": c}
