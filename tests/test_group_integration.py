import pytest

pytestmark = pytest.mark.django_db


def app_labels(app_list):
    return [a["app_label"] for a in app_list]


def models_of(app_list, label):
    app = next(a for a in app_list if a["app_label"] == label)
    return [m["object_name"] for m in app["models"]]


ACCOUNTS_GROUP = {
    "accounts": {
        "display_label": "Accounts",
        "apps": {"auth": ["User", "Group"], "sessions": ["Session"]},
    }
}


def test_index_app_list_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_LIST = {
        "custom_groups": ACCOUNTS_GROUP,
        # Reordering always runs once grouping happens, so pin the group's
        # model order explicitly instead of relying on custom_groups traversal
        # order surviving untouched.
        "order": {"accounts": ["User", "Group", "Session"]},
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert "accounts" in labels
    assert "sessions" not in labels  # fully consumed
    assert models_of(response.context["app_list"], "accounts") == ["User", "Group", "Session"]


def test_sidebar_available_apps_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_LIST = {
        "custom_groups": ACCOUNTS_GROUP,
        "order": {"accounts": ["User", "Group", "Session"]},
    }
    response = admin_client.get("/admin/")
    assert "accounts" in app_labels(response.context["available_apps"])


def test_unpositioned_group_sorts_alphabetically_with_real_apps(admin_client, settings):
    """A group with no ``order`` entry lands alphabetically among real apps —
    the same default an unmentioned real app gets. No more implicit anchor."""
    settings.ADMIN_APP_LIST = {
        "custom_groups": {
            "zzz_group": {"apps": {"auth": ["User", "Group"]}},
        },
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    # "zzz_group"'s display label defaults to "Zzz Group" — alphabetically last.
    assert labels[-1] == "zzz_group"


def test_grouping_composes_with_ordering(admin_client, settings):
    """The synthetic label can be positioned and its models ordered via
    ADMIN_APP_LIST["order"]."""
    settings.ADMIN_APP_LIST = {
        "custom_groups": ACCOUNTS_GROUP,
        "order": {
            "accounts": ["Session", "User", "Group"],  # reorder within the group
            "contenttypes": [],
        },
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert labels[0] == "accounts"  # positioned first
    assert models_of(response.context["app_list"], "accounts") == ["Session", "User", "Group"]


def test_no_group_setting_is_a_noop(admin_client, settings):
    settings.ADMIN_APP_LIST = {"custom_groups": {}}
    response = admin_client.get("/admin/")
    assert "accounts" not in app_labels(response.context["app_list"])
