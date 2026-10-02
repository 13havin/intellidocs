"""create users table

Revision ID: 2069f97fe5a6
Revises: d1fc99d3f2ae
Create Date: 2026-10-02 12:52:58.600978

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2069f97fe5a6'
down_revision: Union[str, Sequence[str], None] = 'd1fc99d3f2ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
