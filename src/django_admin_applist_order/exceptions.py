_EXAMPLE = (
    "    ADMIN_APPS_DISPLAY_ORDER = {\n"
    '        "auth": ["User", "Group"],\n'
    '        "myapp": [],\n'
    "    }"
)


class MalformedDisplayOrderException(Exception):
    """Raised when ADMIN_APPS_DISPLAY_ORDER is not structured correctly.

    The setting must be a dict mapping app labels (str) to lists of model
    names (list[str]). Use the classmethods to construct with a consistent message.
    """

    @classmethod
    def for_setting(cls, value):
        return cls(
            f"ADMIN_APPS_DISPLAY_ORDER must be a dict mapping app labels to lists of "
            f"model names, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_EXAMPLE}"
        )

    @classmethod
    def for_app(cls, app_label, value):
        return cls(
            f"ADMIN_APPS_DISPLAY_ORDER[{app_label!r}] must be a list of model names, "
            f"got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_EXAMPLE}"
        )

    @classmethod
    def for_unknown_model(cls, app_label, model_name, available_models):
        available = sorted(available_models)
        return cls(
            f"ADMIN_APPS_DISPLAY_ORDER[{app_label!r}] contains unknown model {model_name!r}. "
            f"Available models in {app_label!r}: {available}.\n"
            f"Example:\n{_EXAMPLE}"
        )
