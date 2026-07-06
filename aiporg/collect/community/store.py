"""3차: 정규화 저장 (SQLite, 표준 라이브러리).

개인정보 미수집 원칙: 작성자 닉네임/프로필/댓글 본문은 저장하지 않는다.
저장 항목은 site/url/title/body/posted_at/집계수치/keyword 로 한정한다.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass


@dataclass
class CommunityPost:
    site: str
    url: str
    title: str
    body: str
    posted_at: str | None = None
    views: int = 0
    likes: int = 0
    comment_count: int = 0
    keyword: str = ""

    @property
    def url_hash(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:16]


SCHEMA = """
CREATE TABLE IF NOT EXISTS community_posts (
    url_hash     TEXT PRIMARY KEY,
    site         TEXT NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    body         TEXT,
    posted_at    TEXT,
    views        INTEGER DEFAULT 0,
    likes        INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    keyword      TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_site ON community_posts(site);
CREATE INDEX IF NOT EXISTS idx_posted ON community_posts(posted_at);
"""


class CommunityStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        with closing(sqlite3.connect(db_path)) as c:
            c.executescript(SCHEMA)
            c.commit()

    def upsert(self, post: CommunityPost) -> None:
        with closing(sqlite3.connect(self.db_path)) as c:
            c.execute(
                """INSERT INTO community_posts
                   (url_hash, site, url, title, body, posted_at, views, likes,
                    comment_count, keyword)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(url_hash) DO UPDATE SET
                     title=excluded.title, body=excluded.body,
                     views=excluded.views, likes=excluded.likes,
                     comment_count=excluded.comment_count""",
                (post.url_hash, post.site, post.url, post.title, post.body,
                 post.posted_at, post.views, post.likes, post.comment_count, post.keyword),
            )
            c.commit()

    def query(self, keyword: str | None = None, site: str | None = None,
              start: str | None = None, end: str | None = None,
              limit: int = 1000) -> list[CommunityPost]:
        sql = "SELECT site,url,title,body,posted_at,views,likes,comment_count,keyword " \
              "FROM community_posts WHERE 1=1"
        args: list = []
        if site:
            sql += " AND site=?"; args.append(site)
        if keyword:
            sql += " AND (title LIKE ? OR body LIKE ? OR keyword=?)"
            args += [f"%{keyword}%", f"%{keyword}%", keyword]
        if start:
            sql += " AND (posted_at IS NULL OR posted_at>=?)"; args.append(start)
        if end:
            sql += " AND (posted_at IS NULL OR posted_at<=?)"; args.append(end)
        sql += " ORDER BY posted_at DESC LIMIT ?"; args.append(limit)
        with closing(sqlite3.connect(self.db_path)) as c:
            rows = c.execute(sql, args).fetchall()
        return [CommunityPost(*r) for r in rows]

    def count(self) -> int:
        with closing(sqlite3.connect(self.db_path)) as c:
            return c.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
