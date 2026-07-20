"""HealthDoc schema v7: health domains, booking groups, waitlists and rich data.

Revision ID: 20260720_schema_v7
Revises: schema_v6
"""

from alembic import op
import sqlalchemy as sa

revision = "20260720_schema_v7"
down_revision = "schema_v6"
branch_labels = None
depends_on = None


def upgrade():
    # Email is a required registration contact, but it is not an account key:
    # family members and demonstration roles may share one mailbox.
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("users"):
        if constraint.get("column_names") == ["email"] and constraint.get("name"):
            op.drop_constraint(constraint["name"], "users", type_="unique")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table("health_domains", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"), sa.UniqueConstraint("name"))
    op.create_table("indicator_domain_links", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("indicator_dict_id", sa.Integer(), sa.ForeignKey("indicator_dicts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_domain_id", sa.Integer(), sa.ForeignKey("health_domains.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("indicator_dict_id", "health_domain_id", name="uq_indicator_domain_link"))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("friend_relations", sa.Column("booking_auth_status", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("friend_relations", sa.Column("booking_authorized_at", sa.DateTime(timezone=True)))
    op.add_column("institutions", sa.Column("notification_email", sa.String(120)))
    op.add_column("institutions", sa.Column("notification_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    for column in (
        sa.Column("package_type", sa.String(20), nullable=False, server_default="special"),
        sa.Column("audience", sa.String(120)), sa.Column("booking_notice", sa.Text()),
        sa.Column("current_version_id", sa.Integer()),
    ): op.add_column("packages", column)
    op.create_table("package_versions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("package_type", sa.String(20), nullable=False),
        sa.Column("name_snapshot", sa.String(120), nullable=False), sa.Column("price_snapshot", sa.Numeric(10, 2), nullable=False),
        sa.Column("audience_snapshot", sa.String(120)), sa.Column("description_snapshot", sa.Text()),
        sa.Column("booking_notice_snapshot", sa.Text()), sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("package_id", "version_number", name="uq_package_version"))
    op.create_table("package_version_domains", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_version_id", sa.Integer(), sa.ForeignKey("package_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_domain_id", sa.Integer(), sa.ForeignKey("health_domains.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("package_version_id", "health_domain_id", name="uq_package_version_domain"))
    op.create_table("booking_groups", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_code", sa.String(36), nullable=False, unique=True),
        sa.Column("booked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id", ondelete="SET NULL")),
        sa.Column("package_version_id", sa.Integer(), sa.ForeignKey("package_versions.id")),
        sa.Column("appointment_date", sa.Date(), nullable=False), sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("package_name_snapshot", sa.String(120), nullable=False), sa.Column("package_price_snapshot", sa.Numeric(10, 2), nullable=False),
        sa.Column("domain_snapshot", sa.JSON(), nullable=False), sa.Column("booking_notice_snapshot", sa.Text()),
        sa.Column("notice_version_snapshot", sa.Integer()), sa.Column("notice_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contact_snapshot", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for column in (sa.Column("package_version_id", sa.Integer(), sa.ForeignKey("package_versions.id", ondelete="SET NULL")),
                   sa.Column("booking_group_id", sa.Integer(), sa.ForeignKey("booking_groups.id", ondelete="SET NULL")),
                   sa.Column("booked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
                   sa.Column("user_birth_date_snapshot", sa.Date()), sa.Column("user_gender_snapshot", sa.String(20)),
                   sa.Column("user_contact_snapshot", sa.String(120))): op.add_column("appointments", column)
    op.create_table("appointment_events", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False), sa.Column("status_snapshot", sa.String(24), nullable=False),
        sa.Column("message", sa.String(255)), sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("institution_reports", sa.Column("package_version_id", sa.Integer(), sa.ForeignKey("package_versions.id", ondelete="SET NULL")))
    for column in (sa.Column("display_domain_id", sa.Integer(), sa.ForeignKey("health_domains.id")),
        sa.Column("original_name", sa.String(160)), sa.Column("original_value", sa.String(160)),
        sa.Column("original_unit", sa.String(40)), sa.Column("normalized_unit", sa.String(40)),
        sa.Column("reference_text", sa.String(255)), sa.Column("method_snapshot", sa.String(160)),
        sa.Column("abnormal_flag", sa.String(20)), sa.Column("mapping_confidence", sa.Numeric(5, 4)),
        sa.Column("mapping_status", sa.String(30), nullable=False, server_default="confirmed")): op.add_column("report_indicators", column)
    op.create_table("report_text_results", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("institution_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_domain_id", sa.Integer(), sa.ForeignKey("health_domains.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_snapshot", sa.String(120)), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("report_assets", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("institution_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_domain_id", sa.Integer(), sa.ForeignKey("health_domains.id"), nullable=False),
        sa.Column("modality", sa.String(40), nullable=False), sa.Column("title", sa.String(160), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True), sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False), sa.Column("width", sa.Integer()), sa.Column("height", sa.Integer()),
        sa.Column("page_count", sa.Integer()), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("annotation_text", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("report_asset_annotations", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_asset_id", sa.Integer(), sa.ForeignKey("report_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("annotation_type", sa.String(30), nullable=False), sa.Column("geometry", sa.JSON()),
        sa.Column("text", sa.Text()), sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    _create_notification_tables()


def _create_notification_tables():
    op.create_table("appointment_capacity_slots", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False), sa.Column("capacity", sa.Integer()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "appointment_date", name="uq_capacity_slot_date"))
    op.create_table("waitlist_subscriptions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscriber_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_version_id", sa.Integer(), sa.ForeignKey("package_versions.id")), sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False), sa.Column("notification_email", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"), sa.Column("last_satisfied_revision", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.create_table("waitlist_subscription_participants", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("waitlist_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name_snapshot", sa.String(80), nullable=False), sa.Column("health_id_snapshot", sa.String(20), nullable=False),
        sa.Column("booking_authorized_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("subscription_id", "subject_user_id", name="uq_waitlist_participant"))
    op.create_table("availability_notification_events", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("waitlist_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capacity_revision", sa.Integer(), nullable=False), sa.Column("remaining_snapshot", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subscription_id", "capacity_revision", name="uq_availability_event_round"))
    op.create_table("notification_outbox", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(40), nullable=False), sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("recipient", sa.String(120), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_table("notification_deliveries", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbox_id", sa.Integer(), sa.ForeignKey("notification_outbox.id", ondelete="CASCADE"), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False), sa.Column("provider_message_id", sa.String(160)),
        sa.Column("error_message", sa.String(500)), sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    raise RuntimeError("schema v7 contains immutable health-data and booking snapshots; restore the joint database/asset backup instead of downgrading in place")
