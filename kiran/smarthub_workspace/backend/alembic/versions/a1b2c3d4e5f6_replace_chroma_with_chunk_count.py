"""replace chroma_collection with chunk_count

Revision ID: a1b2c3d4e5f6
Revises: 487bde7a8fcd
Create Date: 2026-05-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '487bde7a8fcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    if 'documents' in tables:
        columns = [c['name'] for c in inspector.get_columns('documents')]
        if 'chroma_collection' in columns:
            op.drop_column('documents', 'chroma_collection')
        if 'chunk_count' not in columns:
            op.add_column('documents', sa.Column('chunk_count', sa.Integer(), server_default='0'))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    if 'documents' in tables:
        columns = [c['name'] for c in inspector.get_columns('documents')]
        if 'chunk_count' in columns:
            op.drop_column('documents', 'chunk_count')
        if 'chroma_collection' not in columns:
            op.add_column('documents', sa.Column('chroma_collection', sa.Text(), nullable=True))
