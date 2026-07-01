# Plan: Consolidate `ADMIN_APP_GROUPS` + `ADMIN_APPS_DISPLAY_ORDER` Into One Setting

## STATUS: TODO

## Context

After [[04_add-app-groups-plan]] ships, the package reads **two** independent settings:

- `ADMIN_APP_GROUPS` — merges models from several apps into synthetic groups.
- `ADMIN_APPS_DISPLAY_ORDER` — orders apps and the models within them.

This plan replaces both with a **single** setting, `ADMIN_APP_LIST`, so a project only
ever configures one dict. This is a **breaking change** — old projects must migrate their
settings — so it should ship as its own release, after 0.8.0, not folded into it.

**Design decisions (agreed with the maintainer):**

- New setting name: **`ADMIN_APP_LIST`** (not a reuse/reshape of `ADMIN_APPS_DISPLAY_ORDER`,
  to avoid ambiguity between its old flat shape and a new nested one).
- Two inner keys, both optional and independently emptyable without raising:
  - `"custom_groups"` — exactly the old `ADMIN_APP_GROUPS` value.
  - `"apps"` — exactly the old `ADMIN_APPS_DISPLAY_ORDER` value.
- `ADMIN_APP_GROUPS` and `ADMIN_APPS_DISPLAY_ORDER` are **removed** (not deprecated
  aliases) — this project is pre-1.0, so a clean break plus a README migration note is
  preferable to carrying two settings shapes indefinitely.
- `group.py` / `reorder.py` are untouched: both already take their config as a plain
  argument, so this is purely a `middleware.py` (+ exceptions, settings-reading) change.

**Config shape:**

```python
ADMIN_APP_LIST = {
    "custom_groups": {                 # was ADMIN_APP_GROUPS
        "content": {
            "name": "Content",
            "apps": {"blog": ["Post"], "news": ["Article"]},
        },
    },
    "apps": {                          # was ADMIN_APPS_DISPLAY_ORDER
        "auth": ["User", "Group"],
        "myapp": [],
    },
}
```

Behaviour:

- Missing `ADMIN_APP_LIST` entirely → no-op (same as today).
- `ADMIN_APP_LIST = {}` → no-op.
- Either inner key missing or empty → that half is skipped; the other still runs.
- Grouping still runs before ordering (unchanged composition order).
- `ADMIN_APP_LIST` not a dict, or containing a key other than `"custom_groups"` /
  `"apps"` → raises (genuine misconfiguration, e.g. a typo). Malformed *inner* values
  (e.g. `"apps"` not a dict) continue to be caught by `group_app_list` /
  `reorder_app_list` themselves, which already validate their own argument.

---

## Files to Modify

| File                                    | Action                                                                 |
|------------------------------------------|-------------------------------------------------------------------------|
| `src/.../exceptions.py`                  | Add `MalformedAppListException` for the top-level setting.             |
| `src/.../middleware.py`                 | Read `ADMIN_APP_LIST` instead of the two old settings.                 |
| `tests/settings.py`                     | Update the module-level default to the new nested shape.               |
| `tests/test_middleware_integration.py`  | Update to set `ADMIN_APP_LIST["apps"]` instead of `ADMIN_APPS_DISPLAY_ORDER`. |
| `tests/test_group_integration.py`       | Update to set `ADMIN_APP_LIST["custom_groups"]` instead of `ADMIN_APP_GROUPS`. |
| `tests/test_middleware_settings.py`     | **New.** Unit-ish tests for the top-level `ADMIN_APP_LIST` validation. |
| `README.md`                              | Replace the two setting sections with one; add a migration note.       |
| `pyproject.toml`                         | Bump version (breaking change — maintainer's call: `0.9.0` vs `1.0.0`). |

`group.py` and `reorder.py` need **no changes** — they're pure functions that already
take `app_groups` / `apps_order` as plain arguments.

---

## Step 1 — Write failing tests for the new setting  [ STATUS: TODO ]

Update `tests/test_middleware_integration.py` and `tests/test_group_integration.py` to
configure `ADMIN_APP_LIST` instead of the two old settings, e.g.:

```python
settings.ADMIN_APP_LIST = {
    "apps": {"sessions": [], "auth": ["User", "Group"]},
}
```

```python
settings.ADMIN_APP_LIST = {
    "custom_groups": ACCOUNTS_GROUP,
}
```

And the composition test sets both keys on the same dict:

```python
settings.ADMIN_APP_LIST = {
    "custom_groups": ACCOUNTS_GROUP,
    "apps": {"accounts": ["Session", "User", "Group"], "contenttypes": []},
}
```

Also update `tests/settings.py`'s module-level default:

```python
ADMIN_APP_LIST = {
    "apps": {
        "sessions": [],
        "auth": ["User", "Group"],
    },
}
```

Add `tests/test_middleware_settings.py` for the new top-level validation:

```python
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


def test_only_apps_key_present_still_orders(admin_client, settings):
    settings.ADMIN_APP_LIST = {"apps": {"sessions": [], "auth": ["User", "Group"]}}
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
```

These fail until `MalformedAppListException` and the middleware changes land.

---

## Step 2 — Add `MalformedAppListException`  [ STATUS: TODO ]

In `exceptions.py`, mirroring the existing style:

```python
_APP_LIST_EXAMPLE = (
    "    ADMIN_APP_LIST = {\n"
    '        "custom_groups": {"content": {"apps": {"blog": ["Post"]}}},\n'
    '        "apps": {"auth": ["User", "Group"]},\n'
    "    }"
)

_ALLOWED_APP_LIST_KEYS = {"custom_groups", "apps"}


class MalformedAppListException(Exception):
    """Raised when ADMIN_APP_LIST is not structured correctly.

    The setting must be a dict with only "custom_groups" and/or "apps" keys.
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
```

---

## Step 3 — Update `middleware.py`  [ STATUS: TODO ]

```python
from django.conf import settings

from .exceptions import MalformedAppListException
from .group import group_app_list
from .reorder import reorder_app_list
import logging

_APP_LIST_KEYS = ("app_list", "available_apps")
_ALLOWED_SETTING_KEYS = {"custom_groups", "apps"}

logger = logging.getLogger(__name__)


class AppListOrderMiddleware:
    """Group and/or reorder the admin app list from ``settings.ADMIN_APP_LIST``.

    ``ADMIN_APP_LIST`` has two optional keys:
      * ``"custom_groups"`` — merges models from several apps into synthetic groups.
      * ``"apps"`` — orders apps and the models within them.

    Grouping runs first, so a group's synthetic label can be positioned via "apps".
    If the setting is missing, empty, or both inner keys are empty, this is a no-op.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        app_list_setting = getattr(settings, "ADMIN_APP_LIST", None)
        if not app_list_setting:
            return response

        if not isinstance(app_list_setting, dict):
            raise MalformedAppListException.for_setting(app_list_setting)

        unknown_keys = set(app_list_setting) - _ALLOWED_SETTING_KEYS
        if unknown_keys:
            raise MalformedAppListException.for_unknown_keys(unknown_keys)

        app_groups = app_list_setting.get("custom_groups", {})
        apps_order = app_list_setting.get("apps", {})

        if not app_groups and not apps_order:
            return response

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
```

Note: `.get("custom_groups", {})` (not `.get(...) or {}`) so an explicitly-provided
non-dict value isn't silently swallowed before reaching `group_app_list`'s own
type check — except a falsy-but-wrong-type value (e.g. `"custom_groups": []`), which
is tolerated the same way an empty dict is. That's an accepted, documented edge case,
not a gap worth extra code for.

---

## Step 4 — Update existing tests & README  [ STATUS: TODO ]

- Sweep `tests/test_middleware_integration.py` and `tests/test_group_integration.py` for
  any remaining direct references to `ADMIN_APPS_DISPLAY_ORDER` / `ADMIN_APP_GROUPS` and
  move them under `ADMIN_APP_LIST`.
- `README.md`: replace the "Usage" and "Grouping apps under one title" sections with a
  single `ADMIN_APP_LIST` section, and add a short "Migrating from 0.8.x" block:

  ```python
  # 0.8.x
  ADMIN_APPS_DISPLAY_ORDER = {"auth": ["User", "Group"]}
  ADMIN_APP_GROUPS = {"content": {"apps": {"blog": ["Post"]}}}

  # 0.9.0+
  ADMIN_APP_LIST = {
      "apps": {"auth": ["User", "Group"]},
      "custom_groups": {"content": {"apps": {"blog": ["Post"]}}},
  }
  ```

Run the full suite: `poetry run python -m pytest -v` → all green.

---

## Step 5 — Version bump  [ STATUS: TODO ]

`pyproject.toml`: bump version to reflect a breaking settings change (maintainer's call
between `0.9.0` and `1.0.0`, since the project hasn't hit 1.0 yet).

---

## Step 6 — Release  [ STATUS: TODO ]

After merge, publish to PyPI with clear breaking-change release notes pointing at the
README migration block.

---

## Notes

- `group.py` and `reorder.py` don't change at all — this plan is scoped entirely to how
  `middleware.py` reads settings, plus one new exception.
- Kept `.get(key, {})` semantics (not `or {}`) to avoid masking wrong-type inner values
  with the wrong-key-name check happening first, since unknown top-level keys are a much
  more likely typo than an inner value being deliberately falsy-but-wrong-type.
- After each step is done, change its `[ STATUS: TODO ]` to `[ STATUS: DONE ]`.
