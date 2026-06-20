from django.conf import settings

from .reorder import reorder_app_list
import logging

# Context keys Django populates with the app list: the index page uses
# ``app_list`` and the nav sidebar (each_context) uses ``available_apps``.
_APP_LIST_KEYS = ("app_list", "available_apps")


logger = logging.getLogger(__name__)


class AppListOrderMiddleware:
    """Reorder the admin app list according to ``settings.ADMIN_APPS_DISPLAY_ORDER``.

    This works by post-processing the admin's ``TemplateResponse`` context, so
    it needs no changes to your ``AdminSite`` or to any admin registration.
    Just add it to ``MIDDLEWARE`` and define the setting.

    If the setting is missing or empty, the middleware is a no-op.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        apps_order = getattr(settings, "ADMIN_APPS_DISPLAY_ORDER", None)
        if not apps_order:
            logger.debug("ADMIN_APPS_DISPLAY_ORDER not found in settings.py, skipping")
            return response

        context = getattr(response, "context_data", None)

        if not context:
            return response

        for key in _APP_LIST_KEYS:
            value = context.get(key)
            if isinstance(value, list):
                context[key] = reorder_app_list(value, apps_order)

        return response
