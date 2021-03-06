"""add feed models

Revision ID: ec87ceb571ba
Revises: 
Create Date: 2021-01-18 12:19:53.915458

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec87ceb571ba"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "proxy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("name", sa.UnicodeText(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proxy")),
        sa.UniqueConstraint("url", name=op.f("uq_proxy_url")),
    )
    op.create_table(
        "feed",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("proxy_id", sa.Integer(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("next_check", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proxy_id"],
            ["proxy.id"],
            name=op.f("fk_feed_proxy_id_proxy"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed")),
        sa.UniqueConstraint("url", name=op.f("uq_feed_url")),
    )
    op.create_table(
        "page",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["feed.id"],
            name=op.f("fk_page_feed_id_feed"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page")),
        sa.UniqueConstraint("feed_id", "idx", name=op.f("uq_page_feed_id")),
        sa.UniqueConstraint("url", name=op.f("uq_page_url")),
    )
    op.create_table(
        "post",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guid", sa.Text(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("published", sa.DateTime(), nullable=True),
        sa.Column("updated", sa.DateTime(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("episode", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["feed.id"],
            name=op.f("fk_post_feed_id_feed"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_post_page_id_page"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post")),
        sa.UniqueConstraint("feed_id", "guid", name=op.f("uq_post_feed_id")),
    )
    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.create_index("ix_published", ["feed_id", "published"], unique=False)
        batch_op.create_index(
            "ix_season_episode", ["feed_id", "season", "episode"], unique=False
        )
        batch_op.create_index("ix_updated", ["feed_id", "updated"], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.drop_index("ix_updated")
        batch_op.drop_index("ix_season_episode")
        batch_op.drop_index("ix_published")

    op.drop_table("post")
    op.drop_table("page")
    op.drop_table("feed")
    op.drop_table("proxy")
    # ### end Alembic commands ###
