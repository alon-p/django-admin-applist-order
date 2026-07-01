"""Backward compatibility for the deprecated ADMIN_APP_GROUPS /
ADMIN_APPS_DISPLAY_ORDER settings, superseded by ADMIN_APP_LIST.
"""

import warnings

from .exceptions import MalformedAppListException

_DEPRECATION_MESSAGE = (
    "ADMIN_APP_GROUPS and ADMIN_APPS_DISPLAY_ORDER are deprecated and will be "
    "removed in a future release. Configure ADMIN_APP_LIST instead, e.g.:\n"
    '    ADMIN_APP_LIST = {"custom_groups": {...}, "order": {...}}\n'
    "See the README's migration notes for details."
)


def resolve_app_list_setting(app_list, app_groups, apps_order):
    """Resolve the effective ADMIN_APP_LIST dict, honoring the deprecated
    ADMIN_APP_GROUPS / ADMIN_APPS_DISPLAY_ORDER settings if ADMIN_APP_LIST isn't set.

    ``app_list``, ``app_groups`` and ``apps_order`` are the raw setting values
    (or ``None`` if unset).

    Returns ``(setting, using_legacy)`` — ``setting`` is the dict to validate/use
    (never mutated in place), ``using_legacy`` tells the caller which setting
    name(s) to report in downstream error messages.
    """
    has_legacy = app_groups is not None or apps_order is not None

    if app_list is not None and has_legacy:
        raise MalformedAppListException.for_mixed_legacy_settings()

    if app_list is not None:
        return app_list, False

    if has_legacy:
        warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)
        return {"custom_groups": app_groups or {}, "order": apps_order or {}}, True

    return {}, False
