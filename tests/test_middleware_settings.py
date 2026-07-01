import pytest

from django_admin_applist_order.exceptions import MalformedAppListException

pytestmark = pytest.mark.django_db


def test_missing_setting_is_a_noop(admin_client, settings):
    del settings.ADMIN_APP_LIST
    response = admin_client.get("/admin/")
    assert response.status_code == 200


def test_empty_setting_is_a_noop(admin_client, settings):
    settings.ADMIN_APP_LIST = {}
    response = admin_client.get("/admin/")
    assert response.status_code == 200


def test_setting_not_a_dict_raises(admin_client, settings):
    settings.ADMIN_APP_LIST = ["custom_groups"]
    with pytest.raises(MalformedAppListException):
        admin_client.get("/admin/")


def test_unknown_top_level_key_raises(admin_client, settings):
    settings.ADMIN_APP_LIST = {"customgroups": {}}  # typo: missing underscore
    with pytest.raises(MalformedAppListException):
        admin_client.get("/admin/")


def test_only_order_key_present_still_orders(admin_client, settings):
    settings.ADMIN_APP_LIST = {"order": {"sessions": [], "auth": ["User", "Group"]}}
    response = admin_client.get("/admin/")
    labels = [a["app_label"] for a in response.context["app_list"]]
    assert labels == ["sessions", "auth", "contenttypes"]


def test_only_custom_groups_key_present_still_groups(admin_client, settings):
    settings.ADMIN_APP_LIST = {
        "custom_groups": {
            "accounts": {"apps": {"auth": ["User", "Group"], "sessions": ["Session"]}}
        }
    }
    response = admin_client.get("/admin/")
    labels = [a["app_label"] for a in response.context["app_list"]]
    assert "accounts" in labels
