"""moneda de captura de las operaciones

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADD COLUMN simple: reconstruir la tabla no hace falta y las operaciones quedan intactas.
    op.add_column('trade', sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True))
    op.add_column('trade', sa.Column('fx_rate', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('trade', schema=None) as batch_op:
        batch_op.drop_column('fx_rate')
        batch_op.drop_column('currency')
