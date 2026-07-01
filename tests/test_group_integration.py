import pytest

pytestmark = pytest.mark.django_db


def app_labels(app_list):
    return [a["app_label"] for a in app_list]


def models_of(app_list, label):
    app = next(a for a in app_list if a["app_label"] == label)
    return [m["object_name"] for m in app["models"]]


ACCOUNTS_GROUP = {
    "accounts": {
        "name": "Accounts",
        "apps": {"auth": ["User", "Group"], "sessions": ["Session"]},
    }
}


def test_index_app_list_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    settings.ADMIN_APPS_DISPLAY_ORDER = {}  # isolate grouping from the module's default order
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert "accounts" in labels
    assert "sessions" not in labels  # fully consumed
    assert models_of(response.context["app_list"], "accounts") == ["User", "Group", "Session"]


def test_sidebar_available_apps_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    settings.ADMIN_APPS_DISPLAY_ORDER = {}  # isolate grouping from the module's default order
    response = admin_client.get("/admin/")
    assert "accounts" in app_labels(response.context["available_apps"])


def test_grouping_composes_with_ordering(admin_client, settings):
    """The synthetic label can be positioned and its models ordered via
    ADMIN_APPS_DISPLAY_ORDER."""
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    settings.ADMIN_APPS_DISPLAY_ORDER = {
        "accounts": ["Session", "User", "Group"],  # reorder within the group
        "contenttypes": [],
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert labels[0] == "accounts"  # positioned first
    assert models_of(response.context["app_list"], "accounts") == ["Session", "User", "Group"]


def test_no_group_setting_is_a_noop(admin_client, settings):
    settings.ADMIN_APP_GROUPS = {}
    response = admin_client.get("/admin/")
    assert "accounts" not in app_labels(response.context["app_list"])
