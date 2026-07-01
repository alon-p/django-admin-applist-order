from django.conf import settings

from .exceptions import MalformedDisplayOrderException
from .group import group_app_list
from .reorder import reorder_app_list
import logging

# Context keys Django populates with the app list: the index page uses
# ``app_list`` and the nav sidebar (each_context) uses ``available_apps``.
_APP_LIST_KEYS = ("app_list", "available_apps")


logger = logging.getLogger(__name__)


class AppListOrderMiddleware:
    """Group and/or reorder the admin app list from settings.

    - ``ADMIN_APP_GROUPS`` merges models from several apps into synthetic groups.
    - ``ADMIN_APPS_DISPLAY_ORDER`` orders apps and the models within them.

    This works by post-processing the admin's ``TemplateResponse`` context, so
    it needs no changes to your ``AdminSite`` or to any admin registration.
    Just add it to ``MIDDLEWARE`` and define the setting(s).

    Grouping runs first, so a group's label can be positioned via the order
    setting. If both settings are missing/empty, the middleware is a no-op.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        apps_order = getattr(settings, "ADMIN_APPS_DISPLAY_ORDER", None)
        app_groups = getattr(settings, "ADMIN_APP_GROUPS", None)

        if not apps_order and not app_groups:
            logger.debug(
                "Neither ADMIN_APPS_DISPLAY_ORDER nor ADMIN_APP_GROUPS found in settings.py, "
                "skipping"
            )
            return response

        if apps_order is not None and not isinstance(apps_order, dict):
            raise MalformedDisplayOrderException.for_setting(apps_order)

        context = getattr(response, "context_data", None)

        if not context:
            return response

        for key in _APP_LIST_KEYS:
            value = context.get(key)
            if not isinstance(value, list):
                continue
            if app_groups:
                value = group_app_list(value, app_groups)
            if apps_order:
                value = reorder_app_list(value, apps_order)
            context[key] = value

        return response
