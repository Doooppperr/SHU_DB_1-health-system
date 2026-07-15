from decimal import Decimal

from app.extensions import db


class Institution(db.Model):
    __tablename__ = "institutions"
    __table_args__ = (
        db.UniqueConstraint("name", "branch_name", name="uq_institution_branch"),
        db.CheckConstraint("length(trim(name)) > 0", name="ck_institutions_name_not_blank"),
        db.CheckConstraint("length(trim(branch_name)) > 0", name="ck_institutions_branch_not_blank"),
        db.CheckConstraint("length(trim(address)) > 0", name="ck_institutions_address_not_blank"),
        db.CheckConstraint("length(trim(district)) > 0", name="ck_institutions_district_not_blank"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    branch_name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    district = db.Column(db.String(80), nullable=False)
    metro_info = db.Column(db.String(255), nullable=True)
    consult_phone = db.Column(db.String(30), nullable=True)
    ext = db.Column(db.String(20), nullable=True)
    closed_day = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true(),
    )

    packages = db.relationship("Package", back_populates="institution", cascade="all, delete-orphan")
    administrators = db.relationship(
        "User",
        back_populates="managed_institution",
        foreign_keys="User.managed_institution_id",
    )
    invite = db.relationship(
        "InstitutionInvite",
        back_populates="institution",
        cascade="all, delete-orphan",
        uselist=False,
    )
    images = db.relationship(
        "InstitutionImage",
        back_populates="institution",
        cascade="all, delete-orphan",
        order_by="InstitutionImage.sort_order.asc()",
    )

    @property
    def administrator(self):
        """Compatibility accessor for older presentation helpers."""
        return self.administrators[0] if self.administrators else None

    def to_dict(self):
        image_items = [image.to_dict() for image in self.images]
        cover_image_url = image_items[0]["image_url"] if image_items else self.logo_url
        active_package_count = sum(1 for package in self.packages if package.is_active)
        return {
            "id": self.id,
            "name": self.name,
            "branch_name": self.branch_name,
            "address": self.address,
            "district": self.district,
            "metro_info": self.metro_info,
            "consult_phone": self.consult_phone,
            "ext": self.ext,
            "closed_day": self.closed_day,
            "description": self.description,
            # Keep logo_url as a compatibility alias while clients move to the
            # ordered image collection.  The first image is always the cover.
            "logo_url": cover_image_url,
            "cover_image_url": cover_image_url,
            "images": image_items,
            "is_active": self.is_active,
            "package_count": active_package_count,
            "total_package_count": len(self.packages),
        }


class Package(db.Model):
    __tablename__ = "packages"
    __table_args__ = (
        db.UniqueConstraint("institution_id", "name", name="uq_package_institution_name"),
        db.CheckConstraint("length(trim(name)) > 0", name="ck_packages_name_not_blank"),
        db.CheckConstraint("length(trim(focus_area)) > 0", name="ck_packages_focus_area_not_blank"),
        db.CheckConstraint("gender_scope in ('all', 'male', 'female', 'female_all')", name="ck_packages_gender_scope"),
        db.CheckConstraint("price >= 0", name="ck_packages_price_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    focus_area = db.Column(db.String(120), nullable=False)
    gender_scope = db.Column(db.String(40), nullable=False, default="all")
    price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true(),
    )

    institution = db.relationship("Institution", back_populates="packages")

    def to_dict(self):
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "name": self.name,
            "focus_area": self.focus_area,
            "gender_scope": self.gender_scope,
            "price": float(self.price),
            "description": self.description,
            "is_active": self.is_active,
        }
