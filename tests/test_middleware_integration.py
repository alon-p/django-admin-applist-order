import pytest

from django_admin_applist_order.exceptions import MalformedDisplayOrderException

pytestmark = pytest.mark.django_db


def app_labels(app_list):
    return [app["app_label"] for app in app_list]


def model_names(app_list, app_label):
    app = next(a for a in app_list if a["app_label"] == app_label)
    return [m["object_name"] for m in app["models"]]


def test_index_app_list_is_reordered(admin_client, settings):
    """The admin index `app_list` follows ADMIN_APP_LIST["order"]."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": ["User", "Group"],
        },
    }
    response = admin_client.get("/admin/")

    # Listed apps first, in mapping order; unlisted (contenttypes) after, alpha.
    expected_app_order = ["sessions", "auth", "contenttypes"]
    actual_app_order_from_template = app_labels(response.context["app_list"])
    assert actual_app_order_from_template == expected_app_order


def test_within_app_model_order_is_applied(admin_client, settings):
    """Models inside `auth` follow the per-app order (User before Group)."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": ["User", "Group"],
        },
    }
    response = admin_client.get("/admin/")

    expected_auth_model_order = ["User", "Group"]
    actual_auth_model_order_from_template = model_names(response.context["app_list"], "auth")
    assert actual_auth_model_order_from_template == expected_auth_model_order


def test_sidebar_available_apps_is_reordered(admin_client, settings):
    """The nav sidebar uses `available_apps`; it must be reordered too."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": ["User", "Group"],
        },
    }
    response = admin_client.get("/admin/")

    expected_app_order = ["sessions", "auth", "contenttypes"]
    actual_app_order_from_template = app_labels(response.context["available_apps"])
    assert actual_app_order_from_template == expected_app_order


def test_model_changelist_sidebar_app_order(admin_client, settings):
    """On a model changelist page the sidebar (`available_apps`) is still reordered."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": ["User", "Group"],
        },
    }
    # `app_list` does not exist on sub-pages — only `available_apps` (the sidebar).
    response = admin_client.get("/admin/auth/user/")

    expected_app_order = ["sessions", "auth", "contenttypes"]
    actual_app_order_from_template = app_labels(response.context["available_apps"])
    assert actual_app_order_from_template == expected_app_order


def test_model_changelist_sidebar_model_order(admin_client, settings):
    """On a model changelist page the per-app model order in the sidebar is preserved."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": ["User", "Group"],
        },
    }
    response = admin_client.get("/admin/auth/user/")

    expected_auth_model_order = ["User", "Group"]
    actual_auth_model_order_from_template = model_names(response.context["available_apps"], "auth")
    assert actual_auth_model_order_from_template == expected_auth_model_order


def test_malformed_setting_is_list_not_dict(admin_client, settings):
    """ADMIN_APP_LIST["order"] must be a dict; a list raises MalformedDisplayOrderException."""
    settings.ADMIN_APP_LIST = {"order": ["sessions", "auth"]}  # list, not a dict

    malformed_value = ["sessions", "auth"]
    with pytest.raises(MalformedDisplayOrderException) as exc_info:
        admin_client.get("/admin/")

    assert str(malformed_value) in str(exc_info.value)


def test_malformed_setting_model_list_is_none(admin_client, settings):
    """A None model list raises MalformedDisplayOrderException naming the offending app."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": None,  # None instead of a list
        },
    }

    with pytest.raises(MalformedDisplayOrderException) as exc_info:
        admin_client.get("/admin/")

    assert "auth" in str(exc_info.value)


def test_malformed_setting_model_list_is_string(admin_client, settings):
    """A string model list raises MalformedDisplayOrderException naming the offending app."""
    settings.ADMIN_APP_LIST = {
        "order": {
            "sessions": [],
            "auth": "User",  # string instead of a list
        },
    }

    with pytest.raises(MalformedDisplayOrderException) as exc_info:
        admin_client.get("/admin/")

    assert "auth" in str(exc_info.value)


def test_unknown_model_in_setting_is_skipped_and_logs(admin_client, settings, caplog):
    """A model in the config that doesn't exist for this user is silently skipped,
    the response succeeds, and a DEBUG log names the missing model and app."""
    import logging

    settings.ADMIN_APP_LIST = {
        "order": {
            "auth": ["GhostModel", "User", "Group"],
        },
    }
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.reorder"):
        response = admin_client.get("/admin/")

    assert response.status_code == 200
    actual_auth_model_order = model_names(response.context["app_list"], "auth")
    assert actual_auth_model_order == ["User", "Group"]
    assert any(
        "ghostmodel" in record.message.lower() and "auth" in record.message.lower()
        for record in caplog.records
    )


def test_default_order_differs_without_setting(admin_client, settings):
    """Sanity check: with the setting empty, order is Django's default,
    proving our other assertions are caused by the middleware."""
    settings.ADMIN_APP_LIST = {}
    response = admin_client.get("/admin/")

    # Django sorts by verbose_name_plural: "groups" < "users", so Group comes first.
    expected_auth_model_order = ["Group", "User"]
    actual_auth_model_order_from_template = model_names(response.context["app_list"], "auth")
    assert actual_auth_model_order_from_template == expected_auth_model_order
