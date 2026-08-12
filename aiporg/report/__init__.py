"""보고서 생성 계층 (PRD 8·10항)."""


def write_docx(*args, **kwargs):
    from .docx_writer import write_docx as _write_docx

    return _write_docx(*args, **kwargs)


def write_html(*args, **kwargs):
    from .html_writer import write_html as _write_html

    return _write_html(*args, **kwargs)


def write_markdown(*args, **kwargs):
    from .markdown_writer import write_markdown as _write_markdown

    return _write_markdown(*args, **kwargs)


def write_keyword_docx(*args, **kwargs):
    from .keyword_docx_writer import write_keyword_docx as _write_keyword_docx

    return _write_keyword_docx(*args, **kwargs)


__all__ = ["write_docx", "write_html", "write_keyword_docx", "write_markdown"]
