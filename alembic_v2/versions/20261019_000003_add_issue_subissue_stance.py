"""Add stance (policy agree/disagree) to issue_subissues.

Revision ID: 20261019_000003
Revises: 20261019_000002
Create Date: 2026-10-19 00:00:03

Sentiment (general positive/negative/neutral/mixed tone) and stance
(policy support/oppose) are two separate axes -- requirements doc §4.3:
"정책 찬반과 일반 감성도 별도 개념으로 다룬다". issue_subissues.sentiment
previously existed but was hardcoded NEUTRAL by IssueFinalizationService;
this migration adds the column stance needs to exist alongside it, now
that both are computed by a real classifier (app/sentiment/service.py).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261019_000003"
down_revision: Union[str, Sequence[str], None] = "20261019_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STANCE = sa.Enum(
    "SUPPORT", "OPPOSE", "NEUTRAL", "MIXED", "NOT_APPLICABLE", name="stance_label",
)


def upgrade() -> None:
    STANCE.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("issue_subissues") as batch_op:
        batch_op.add_column(
            sa.Column(
                "stance", STANCE, nullable=False,
                server_default="NOT_APPLICABLE",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("issue_subissues") as batch_op:
        batch_op.drop_column("stance")
    STANCE.drop(op.get_bind(), checkfirst=True)
