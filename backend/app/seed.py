import os
from decimal import Decimal

from app.extensions import db
from app.models import IndicatorCategory, IndicatorDict, Institution, Package, User


INSTITUTION_SEEDS = [
    {
        "name": "美年大健康",
        "branch_name": "小木桥分院(美年门诊部)",
        "district": "徐汇区",
        "address": "小木桥路251号天亿大厦1-3楼",
        "metro_info": "4号线大木桥路站3号口，12号线嘉善路站4号口",
        "consult_phone": "64031188",
        "closed_day": "周一休",
        "description": "综合体检服务中心",
    },
    {
        "name": "美年大健康",
        "branch_name": "苏河分院(美恒门诊部)",
        "district": "静安区",
        "address": "恒丰路638号苏河一号3楼",
        "metro_info": "1/3/4号线上海火车站站3号口",
        "consult_phone": "63810221",
        "closed_day": "周四休",
        "description": "靠近交通枢纽，支持快速预约",
    },
    {
        "name": "美年大健康",
        "branch_name": "五角场分院(美阳门诊部)",
        "district": "杨浦区",
        "address": "淞沪路388号创智天地7号楼5楼",
        "metro_info": "10号线江湾体育场站11号口",
        "consult_phone": "35360351",
        "closed_day": "周五休",
        "description": "常规筛查与专项体检并行",
    },
]


PACKAGE_TEMPLATE = [
    {
        "name": "A套餐-综合套餐",
        "focus_area": "全身基础筛查",
        "gender_scope": "all",
        "price": Decimal("699.00"),
        "description": "覆盖常规体格检查、血常规、尿常规、肝肾功能与基础影像。",
    },
    {
        "name": "B套餐-心脑血管",
        "focus_area": "心脑血管风险",
        "gender_scope": "all",
        "price": Decimal("999.00"),
        "description": "强化血脂、炎症指标、超声与心电检查。",
    },
    {
        "name": "C套餐-内分泌",
        "focus_area": "糖脂代谢与甲状腺",
        "gender_scope": "all",
        "price": Decimal("1199.00"),
        "description": "覆盖血糖、胰岛素、糖化血红蛋白及甲状腺功能。",
    },
    {
        "name": "D套餐-消化及呼吸",
        "focus_area": "消化系统与肺功能",
        "gender_scope": "all",
        "price": Decimal("1099.00"),
        "description": "包含幽门螺旋杆菌、消化功能及肺功能筛查。",
    },
    {
        "name": "E套餐-女性专项",
        "focus_area": "女性健康",
        "gender_scope": "female_all",
        "price": Decimal("1299.00"),
        "description": "增加妇科专项、乳腺与甲状腺针对性评估。",
    },
]


INDICATOR_CATEGORY_SEEDS = [
    {"name": "一般检查", "sort_order": 1},
    {"name": "血糖", "sort_order": 2},
    {"name": "血脂", "sort_order": 3},
    {"name": "肝功能", "sort_order": 4},
    {"name": "肾功能", "sort_order": 5},
]


INDICATOR_DICT_SEEDS = [
    {
        "category": "一般检查",
        "code": "BMI",
        "name": "体重指数",
        "aliases": ["BMI", "体重指数"],
        "unit": "kg/m²",
        "reference_low": Decimal("18.50"),
        "reference_high": Decimal("23.90"),
        "clinical_significance": "过高提示超重或肥胖风险。",
        "value_type": "numeric",
    },
    {
        "category": "血糖",
        "code": "FBG",
        "name": "空腹血糖",
        "aliases": ["空腹血糖", "FBG", "GLU"],
        "unit": "mmol/L",
        "reference_low": Decimal("3.90"),
        "reference_high": Decimal("6.10"),
        "clinical_significance": "升高提示糖代谢异常风险。",
        "value_type": "numeric",
    },
    {
        "category": "血脂",
        "code": "TC",
        "name": "总胆固醇",
        "aliases": ["总胆固醇", "TC"],
        "unit": "mmol/L",
        "reference_low": Decimal("0.00"),
        "reference_high": Decimal("5.20"),
        "clinical_significance": "升高提示动脉粥样硬化风险上升。",
        "value_type": "numeric",
    },
    {
        "category": "血脂",
        "code": "TG",
        "name": "甘油三酯",
        "aliases": ["甘油三酯", "TG"],
        "unit": "mmol/L",
        "reference_low": Decimal("0.00"),
        "reference_high": Decimal("1.70"),
        "clinical_significance": "升高与代谢综合征风险相关。",
        "value_type": "numeric",
    },
    {
        "category": "血脂",
        "code": "HDL",
        "name": "高密度脂蛋白",
        "aliases": ["高密度脂蛋白", "HDL"],
        "unit": "mmol/L",
        "reference_low": Decimal("1.00"),
        "reference_high": Decimal("2.30"),
        "clinical_significance": "偏低提示心血管保护作用下降。",
        "value_type": "numeric",
    },
    {
        "category": "血脂",
        "code": "LDL",
        "name": "低密度脂蛋白",
        "aliases": ["低密度脂蛋白", "LDL"],
        "unit": "mmol/L",
        "reference_low": Decimal("0.00"),
        "reference_high": Decimal("3.40"),
        "clinical_significance": "偏高提示心脑血管风险增加。",
        "value_type": "numeric",
    },
    {
        "category": "肝功能",
        "code": "ALT",
        "name": "丙氨酸氨基转移酶",
        "aliases": ["ALT", "谷丙转氨酶", "丙氨酸氨基转移酶"],
        "unit": "U/L",
        "reference_low": Decimal("0.00"),
        "reference_high": Decimal("40.00"),
        "clinical_significance": "升高提示肝细胞损伤可能。",
        "value_type": "numeric",
    },
    {
        "category": "肝功能",
        "code": "AST",
        "name": "天门冬氨酸氨基转移酶",
        "aliases": ["AST", "谷草转氨酶", "天门冬氨酸氨基转移酶"],
        "unit": "U/L",
        "reference_low": Decimal("0.00"),
        "reference_high": Decimal("40.00"),
        "clinical_significance": "升高需结合ALT等指标评估。",
        "value_type": "numeric",
    },
    {
        "category": "肾功能",
        "code": "UA",
        "name": "尿酸",
        "aliases": ["尿酸", "UA"],
        "unit": "μmol/L",
        "reference_low": Decimal("155.00"),
        "reference_high": Decimal("428.00"),
        "clinical_significance": "升高提示高尿酸血症风险。",
        "value_type": "numeric",
    },
    {
        "category": "肾功能",
        "code": "CREA",
        "name": "肌酐",
        "aliases": ["肌酐", "CREA"],
        "unit": "μmol/L",
        "reference_low": Decimal("44.00"),
        "reference_high": Decimal("133.00"),
        "clinical_significance": "异常提示肾功能变化风险。",
        "value_type": "numeric",
    },
]


def seed_institutions_and_packages():
    if Institution.query.first() is not None:
        return

    for institution_payload in INSTITUTION_SEEDS:
        institution = Institution(**institution_payload)
        db.session.add(institution)
        db.session.flush()

        for package_payload in PACKAGE_TEMPLATE:
            package = Package(institution_id=institution.id, **package_payload)
            db.session.add(package)

    db.session.commit()


def seed_indicator_dicts():
    if IndicatorDict.query.first() is not None:
        return

    category_map = {}
    for category_payload in INDICATOR_CATEGORY_SEEDS:
        category = IndicatorCategory(
            name=category_payload["name"],
            sort_order=category_payload["sort_order"],
        )
        db.session.add(category)
        db.session.flush()
        category_map[category.name] = category

    for item in INDICATOR_DICT_SEEDS:
        category = category_map[item["category"]]
        indicator = IndicatorDict(
            category_id=category.id,
            code=item["code"],
            name=item["name"],
            aliases=item["aliases"],
            unit=item["unit"],
            reference_low=item["reference_low"],
            reference_high=item["reference_high"],
            clinical_significance=item["clinical_significance"],
            value_type=item["value_type"],
        )
        db.session.add(indicator)

    db.session.commit()


def seed_core_data():
    seed_admin_user()
    seed_institutions_and_packages()
    seed_indicator_dicts()


def seed_admin_user():
    default_admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin").strip()
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123").strip()
    default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com").strip()

    if not default_admin_username or not default_admin_password:
        return

    admin = User.query.filter_by(username=default_admin_username).first()
    if admin is not None:
        if admin.role != "admin":
            admin.role = "admin"
            db.session.commit()
        return

    admin = User(
        username=default_admin_username,
        email=default_admin_email or None,
        role="admin",
    )
    admin.set_password(default_admin_password)
    db.session.add(admin)
    db.session.commit()
