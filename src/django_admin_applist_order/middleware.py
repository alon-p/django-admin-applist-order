from django.conf import settings

from .exceptions import MalformedAppListException
from .group import group_app_list
from .legacy import resolve_app_list_setting
from .reorder import reorder_app_list
import logging

# Context keys Django populates with the app list: the index page uses
# ``app_list`` and the nav sidebar (each_context) uses ``available_apps``.
_APP_LIST_KEYS = ("app_list", "available_apps")
_ALLOWED_SETTING_KEYS = {"custom_groups", "order"}


logger = logging.getLogger(__name__)


class AppListOrderMiddleware:
    """Group and/or reorder the admin app list from ``settings.ADMIN_APP_LIST``.

    ``ADMIN_APP_LIST`` has two optional keys:
      * ``"custom_groups"`` — merges models from several apps into synthetic groups.
      * ``"order"`` — orders apps and the models within them.

    This works by post-processing the admin's ``TemplateResponse`` context, so
    it needs no changes to your ``AdminSite`` or to any admin registration.
    Just add it to ``MIDDLEWARE`` and define the setting.

    Grouping runs first, so a group's synthetic label can be positioned via "order".
    If the setting is missing, empty, or both inner keys are empty, this is a no-op.

    The deprecated ``ADMIN_APP_GROUPS`` / ``ADMIN_APPS_DISPLAY_ORDER`` settings are
    still honored if ``ADMIN_APP_LIST`` isn't set, with a DeprecationWarning.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        app_list_setting, using_legacy = resolve_app_list_setting(
            getattr(settings, "ADMIN_APP_LIST", None),
            getattr(settings, "ADMIN_APP_GROUPS", None),
            getattr(settings, "ADMIN_APPS_DISPLAY_ORDER", None),
        )
        if not app_list_setting:
            logger.debug(
                "Neither ADMIN_APP_LIST nor the deprecated ADMIN_APPS_DISPLAY_ORDER/"
                "ADMIN_APP_GROUPS found in settings.py, skipping"
            )
            return response

        if not isinstance(app_list_setting, dict):
            raise MalformedAppListException.for_setting(app_list_setting)

        unknown_keys = set(app_list_setting) - _ALLOWED_SETTING_KEYS
        if unknown_keys:
            raise MalformedAppListException.for_unknown_keys(unknown_keys)

        app_groups = app_list_setting.get("custom_groups", {})
        apps_order = app_list_setting.get("order", {})

        if not app_groups and not apps_order:
            return response

        context = getattr(response, "context_data", None)
        if not context:
            return response

        groups_setting_name = "ADMIN_APP_GROUPS" if using_legacy else 'ADMIN_APP_LIST["custom_groups"]'
        order_setting_name = "ADMIN_APPS_DISPLAY_ORDER" if using_legacy else 'ADMIN_APP_LIST["order"]'

        for key in _APP_LIST_KEYS:
            value = context.get(key)
            if not isinstance(value, list):
                continue
            if app_groups:
                value = group_app_list(value, app_groups, setting_name=groups_setting_name)
            if app_groups or apps_order:
                value = reorder_app_list(value, apps_order, setting_name=order_setting_name)
            context[key] = value

        return response
