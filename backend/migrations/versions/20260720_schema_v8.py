"""HealthDoc schema v8: organization subjects and cross-branch report audit.

Revision ID: 20260720_schema_v8
Revises: 20260720_schema_v7
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_schema_v8"
down_revision = "20260720_schema_v7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("service_features", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_not_blank"),
    )
    op.add_column("institutions", sa.Column("organization_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT name, MIN(id) AS first_id FROM institutions GROUP BY name ORDER BY first_id")).fetchall()
    for index, row in enumerate(rows, start=1):
        bind.execute(sa.text(
            "INSERT INTO organizations (id, name, description, service_features, is_active, created_at) "
            "VALUES (:id, :name, :description, :features, true, CURRENT_TIMESTAMP)"
        ), {"id": index, "name": row.name, "description": f"{row.name}旗下体检服务机构。", "features": "[]"})
        bind.execute(sa.text("UPDATE institutions SET organization_id=:id WHERE name=:name"), {"id": index, "name": row.name})
    op.alter_column("institutions", "organization_id", nullable=False)
    op.create_foreign_key("fk_institutions_organization", "institutions", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_institutions_organization_id", "institutions", ["organization_id"])
    op.drop_constraint("uq_institution_branch", "institutions", type_="unique")
    op.create_unique_constraint("uq_institution_branch", "institutions", ["organization_id", "branch_name"])
    op.create_table(
        "report_access_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("actor_institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), index=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("institution_reports.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), index=True),
        sa.Column("access_type", sa.String(20), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.CheckConstraint("access_type in ('detail', 'asset')", name="ck_report_access_logs_type"),
    )


def downgrade():
    raise RuntimeError("schema v8 contains cross-branch health-data access audit; restore a complete backup instead of downgrading in place")
