from app.models import (
    Comment,
    FriendRelation,
    HealthIndicator,
    HealthRecord,
    IndicatorCategory,
    IndicatorDict,
    Institution,
    Package,
    User,
)


def _constraint_names(model):
    return {constraint.name for constraint in model.__table__.constraints}


def test_database_check_constraints_are_registered():
    expected = {
        User: {"ck_users_role", "ck_users_username_not_blank"},
        FriendRelation: {"ck_friend_not_self", "ck_friend_relation_name_not_blank"},
        Comment: {"ck_comments_rating_range", "ck_comments_content_not_blank"},
        IndicatorCategory: {"ck_indicator_categories_name_not_blank"},
        IndicatorDict: {
            "ck_indicator_dicts_code_not_blank",
            "ck_indicator_dicts_name_not_blank",
            "ck_indicator_dicts_value_type",
            "ck_indicator_dicts_reference_range",
        },
        Institution: {
            "ck_institutions_name_not_blank",
            "ck_institutions_branch_not_blank",
            "ck_institutions_address_not_blank",
            "ck_institutions_district_not_blank",
        },
        Package: {
            "ck_packages_name_not_blank",
            "ck_packages_focus_area_not_blank",
            "ck_packages_gender_scope",
            "ck_packages_price_non_negative",
        },
        HealthRecord: {"ck_health_records_status"},
        HealthIndicator: {"ck_health_indicators_value_not_blank", "ck_health_indicators_source"},
    }

    for model, constraint_names in expected.items():
        assert constraint_names <= _constraint_names(model)
