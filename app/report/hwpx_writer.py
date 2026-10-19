"""Minimal 3-page HWPX prototype: cover, native TOC, summary.

Builds on the approved contracts only (``docs/aiporg2/visualization-design.md``,
16차): a ``ReportSchema`` (the approval record), the ``NarrativeOutputSchema``
version it was approved with, and the ``VisualizationOutputSchema`` for each
required slot. Every sentence and number on the page is copied verbatim from
those already-approved contracts -- this module invents no new fact or number
(AGENTS.md rule 6) and never calls an LLM or the network.

Uses the upstream ``python-hwpx`` package (pinned in requirements.txt,
docs/aiporg2/visualization-design.md / HANDOFF.md "HWPX 구현 방향") to produce
real HWPX bytes. This has NOT been opened in actual Hancom Office from this
environment -- that verification still needs a human with the real editor
(see HANDOFF.md 16차 "검증 못 한 부분").
"""

from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from hwpx import HwpxDocument
from hwpx.tools.toc_author import add_native_toc, mark_toc_dirty

from app.schemas.narrative import NarrativeOutputSchema
from app.schemas.report import ReportSchema
from app.schemas.visualization import VisualizationOutputSchema
from app.visualization.service import CHANNEL_DONUT_SLOT, TOP10_KEYWORDS_SLOT

REQUIRED_SLOTS = (CHANNEL_DONUT_SLOT, TOP10_KEYWORDS_SLOT)


class HwpxPrototypeError(ValueError):
    """Raised when the given inputs cannot produce the prototype."""


def build_cover_toc_summary(
    report: ReportSchema,
    narrative_output: NarrativeOutputSchema,
    visualization_outputs: dict[str, VisualizationOutputSchema],
    *,
    title: str,
    subtitle: str = "AIPORG 2.0 자동 생성 시제품 — 원본 표지 디자인 자산 미확보",
) -> bytes:
    missing = [slot for slot in REQUIRED_SLOTS if slot not in visualization_outputs]
    if missing:
        raise HwpxPrototypeError(f"missing visualization slots: {missing}")

    doc = HwpxDocument.new()

    doc.add_paragraph(title, style="본문")
    doc.add_paragraph(subtitle, style="본문")
    doc.add_paragraph(f"승인 시각: {report.run.created_at.isoformat()}", style="본문")

    toc_insert_index = len(doc.paragraphs)

    summary_heading = doc.add_heading("요약", level=1)
    for sentence in narrative_output.sentences:
        doc.add_paragraph(sentence.text, style="본문")

    donut = visualization_outputs[CHANNEL_DONUT_SLOT]
    doc.add_heading(donut.title, level=2)
    _add_channel_donut(doc, donut)

    cards = visualization_outputs[TOP10_KEYWORDS_SLOT]
    doc.add_heading(cards.title, level=2)
    _add_keyword_table(doc, cards)

    add_native_toc(doc, at_index=toc_insert_index, title="<목차>")
    mark_toc_dirty(doc)

    toc_open_paragraph = doc.paragraphs[toc_insert_index]
    doc.styles.apply_paragraph_format(paragraphs=[toc_open_paragraph], page_break_before=True)
    doc.styles.apply_paragraph_format(paragraphs=[summary_heading], page_break_before=True)

    return doc.to_bytes()


def _add_channel_donut(doc: HwpxDocument, donut: VisualizationOutputSchema) -> None:
    included = [item for item in sorted(donut.items, key=lambda item: item.order) if item.included]
    if not included:
        doc.add_paragraph("표시할 채널 항목이 없다.", style="본문")
        return
    figure, axis = plt.subplots(figsize=(4, 4))
    axis.pie(
        [item.value for item in included],
        labels=[item.label for item in included],
        autopct="%1.0f%%",
    )
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=150)
    plt.close(figure)
    doc.add_picture(buffer.getvalue(), "png", width_mm=80, height_mm=80)


def _add_keyword_table(doc: HwpxDocument, cards: VisualizationOutputSchema) -> None:
    included = [item for item in sorted(cards.items, key=lambda item: item.order) if item.included]
    if not included:
        doc.add_paragraph("표시할 키워드 항목이 없다.", style="본문")
        return
    table = doc.add_table(rows=len(included) + 1, cols=2)
    table.set_cell_text(0, 0, "순위")
    table.set_cell_text(0, 1, "키워드")
    for row, item in enumerate(included, start=1):
        table.set_cell_text(row, 0, str(row))
        table.set_cell_text(row, 1, item.label)
