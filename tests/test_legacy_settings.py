import pytest

from django_admin_applist_order.exceptions import MalformedAppListException

pytestmark = pytest.mark.django_db


def test_legacy_apps_display_order_still_works(admin_client, settings):
    del settings.ADMIN_APP_LIST
    settings.ADMIN_APPS_DISPLAY_ORDER = {"sessions": [], "auth": ["User", "Group"]}
    with pytest.warns(DeprecationWarning):
        response = admin_client.get("/admin/")
    labels = [a["app_label"] for a in response.context["app_list"]]
    assert labels == ["sessions", "auth", "contenttypes"]


def test_legacy_app_groups_still_works(admin_client, settings):
    del settings.ADMIN_APP_LIST
    settings.ADMIN_APP_GROUPS = {
        "accounts": {"apps": {"auth": ["User", "Group"], "sessions": ["Session"]}}
    }
    with pytest.warns(DeprecationWarning):
        response = admin_client.get("/admin/")
    labels = [a["app_label"] for a in response.context["app_list"]]
    assert "accounts" in labels


def test_mixing_new_and_legacy_settings_raises(admin_client, settings):
    settings.ADMIN_APP_LIST = {"order": {"auth": ["User", "Group"]}}
    settings.ADMIN_APPS_DISPLAY_ORDER = {"auth": ["User", "Group"]}
    with pytest.raises(MalformedAppListException):
        admin_client.get("/admin/")


def test_legacy_error_message_names_the_legacy_setting(admin_client, settings):
    del settings.ADMIN_APP_LIST
    settings.ADMIN_APPS_DISPLAY_ORDER = {"auth": "not-a-list"}
    with pytest.warns(DeprecationWarning):
        with pytest.raises(Exception, match="ADMIN_APPS_DISPLAY_ORDER"):
            admin_client.get("/admin/")


def test_new_setting_error_message_names_the_new_setting(admin_client, settings):
    settings.ADMIN_APP_LIST = {"order": "not-a-dict"}
    with pytest.raises(Exception, match=r'ADMIN_APP_LIST\["order"\]'):
        admin_client.get("/admin/")
