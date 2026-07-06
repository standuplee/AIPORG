"""보고서 생성 계층 (PRD 8·10항).

ReportModel + 차트 -> DOCX/HTML/Markdown. 원본 리포트의 절 구성(Ⅰ~Ⅵ)과
표/그림 배치를 재현한다.
"""
from .docx_writer import write_docx
from .html_writer import write_html
from .markdown_writer import write_markdown

__all__ = ["write_docx", "write_html", "write_markdown"]
