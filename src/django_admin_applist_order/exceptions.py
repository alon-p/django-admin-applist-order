_APP_LIST_EXAMPLE = (
    "    ADMIN_APP_LIST = {\n"
    '        "custom_groups": {"content": {"apps": {"blog": ["Post"]}}},\n'
    '        "order": {"auth": ["User", "Group"]},\n'
    "    }"
)

_ALLOWED_APP_LIST_KEYS = {"custom_groups", "order"}


class MalformedDisplayOrderException(Exception):
    """Raised when the app-ordering setting is not structured correctly.

    The setting must be a dict mapping app labels (str) to lists of model
    names (list[str]). Use the classmethods to construct with a consistent message.
    """

    @classmethod
    def for_setting(cls, value, setting_name="ADMIN_APPS_DISPLAY_ORDER"):
        return cls(
            f"{setting_name} must be a dict mapping app labels to lists of "
            f"model names, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_app(cls, app_label, value, setting_name="ADMIN_APPS_DISPLAY_ORDER"):
        return cls(
            f"{setting_name}[{app_label!r}] must be a list of model names, "
            f"got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_unknown_model(cls, app_label, model_name, available_models, setting_name="ADMIN_APPS_DISPLAY_ORDER"):
        available = sorted(available_models)
        return cls(
            f"{setting_name}[{app_label!r}] contains unknown model {model_name!r}. "
            f"Available models in {app_label!r}: {available}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )


class MalformedAppGroupsException(Exception):
    """Raised when the app-groups setting is not structured correctly.

    The setting must be a dict mapping a synthetic app label (str) to a group
    definition: a dict with an ``"apps"`` mapping of ``{app_label: [model, ...]}``
    and an optional ``"display_label"`` display title.
    """

    @classmethod
    def for_setting(cls, value, setting_name="ADMIN_APP_GROUPS"):
        return cls(
            f"{setting_name} must be a dict mapping group labels to group "
            f"definitions, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_group(cls, group_label, value, setting_name="ADMIN_APP_GROUPS"):
        return cls(
            f"{setting_name}[{group_label!r}] must be a dict with an 'apps' mapping, "
            f"got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_app(cls, group_label, app_label, value, setting_name="ADMIN_APP_GROUPS"):
        return cls(
            f"{setting_name}[{group_label!r}]['apps'][{app_label!r}] must be a list of "
            f"model names, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )


class MalformedAppListException(Exception):
    """Raised when ADMIN_APP_LIST is not structured correctly, or is combined
    with the deprecated ADMIN_APP_GROUPS / ADMIN_APPS_DISPLAY_ORDER settings.
    """

    @classmethod
    def for_setting(cls, value):
        return cls(
            f"ADMIN_APP_LIST must be a dict, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_unknown_keys(cls, unknown_keys):
        return cls(
            f"ADMIN_APP_LIST only supports the keys {sorted(_ALLOWED_APP_LIST_KEYS)!r}, "
            f"got unexpected key(s): {sorted(unknown_keys)!r}.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )

    @classmethod
    def for_mixed_legacy_settings(cls):
        return cls(
            "ADMIN_APP_LIST cannot be combined with the deprecated ADMIN_APP_GROUPS "
            "or ADMIN_APPS_DISPLAY_ORDER settings. Remove the deprecated settings and "
            "configure everything through ADMIN_APP_LIST.\n"
            f"Example:\n{_APP_LIST_EXAMPLE}"
        )
