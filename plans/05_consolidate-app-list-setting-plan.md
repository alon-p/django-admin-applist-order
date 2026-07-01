# Plan: Consolidate `ADMIN_APP_GROUPS` + `ADMIN_APPS_DISPLAY_ORDER` Into One Setting

## STATUS: DONE

## Addendum — top-level `"apps"` renamed to `"order"`

Everything below was written and implemented with the top-level ordering key named
`"apps"` (i.e. `ADMIN_APP_LIST["apps"]`). After implementation, that was revisited:
`"apps"` was ambiguous with the *nested* `custom_groups[...]["apps"]` key (source apps
feeding a synthetic group) — same name, two different meanings one nesting level apart.

**Final shape ships with the top-level key renamed to `"order"`:**

```python
ADMIN_APP_LIST = {
    "order": {"auth": ["User", "Group"]},              # was "apps" below
    "custom_groups": {
        "content": {"apps": {"blog": ["Post"]}},        # unchanged — group's source apps
    },
}
```

This was the cheaper of the two disambiguation options: it only touches
`middleware.py`'s key lookup (`.get("apps", {})` → `.get("order", {})`), the
legacy-conversion mapping in `legacy.py`, and the exception examples/`_ALLOWED_APP_LIST_KEYS`
— `group.py`'s expected shape (and thus the legacy `ADMIN_APP_GROUPS` shape) never changes.
All code and docs are updated accordingly; the snippets further down in this file still
say `"apps"` for the top-level key and are kept as-is for historical record rather than
mechanically edited (risk of also touching the nested `"apps"` key, which did *not*
change).

## Addendum — group definition's `"name"` renamed to `"display_label"`

A second naming fix, same rationale: the group-definition key that supplies the
synthetic group's display title (e.g. `{"content": {"name": "Content", "apps": {...}}}`)
was renamed to `"display_label"`, since `"name"` sat too close to the dict's own key
(`group_label` in code — `"content"` in the example) for a reader to tell them apart.

```python
ADMIN_APP_LIST = {
    "custom_groups": {
        "content": {"display_label": "Content", "apps": {"blog": ["Post"]}},  # was "name"
    },
}
```

Scope is deliberately narrow: this only changes the **input** key `group_app_list` reads
(`definition.get("display_label")` in `group.py`). It does *not* touch the **output**
shape — the synthetic app dict `_make_group()` builds still has a `"name"` key, because
that has to match the dict shape Django itself produces for every real app (`app["name"]`
is read directly by Django's admin templates). Renaming the config's input key while
keeping Django's own `"name"` output key intact is what avoids confusing the two: config
in uses `display_label`, Django's rendered shape out still uses `name`.

Since this whole `ADMIN_APP_GROUPS`/`custom_groups` feature is unreleased (no git tags,
no PyPI release yet), there's no legacy `"name"`-key config in the wild to keep working —
so `group_app_list` reads `"display_label"` unconditionally, for both the
`ADMIN_APP_LIST["custom_groups"]` and legacy `ADMIN_APP_GROUPS` entry points.

## Context

After [[04_add-app-groups-plan]] ships, the package reads **two** independent settings:

- `ADMIN_APP_GROUPS` — merges models from several apps into synthetic groups.
- `ADMIN_APPS_DISPLAY_ORDER` — orders apps and the models within them.

This plan introduces a **single** setting, `ADMIN_APP_LIST`, so a project only ever
configures one dict going forward. Unlike the original version of this plan, this is
**not** a breaking change: `ADMIN_APP_GROUPS` and `ADMIN_APPS_DISPLAY_ORDER` keep working
exactly as before, but using them now emits a `DeprecationWarning` pointing at
`ADMIN_APP_LIST`. Because nothing breaks, this can ship as a minor release rather than
waiting for a major-version cutover.

**Design decisions (agreed with the maintainer):**

- New setting name: **`ADMIN_APP_LIST`** (not a reuse/reshape of `ADMIN_APPS_DISPLAY_ORDER`,
  to avoid ambiguity between its old flat shape and a new nested one).
- Two inner keys, both optional and independently emptyable without raising:
  - `"custom_groups"` — exactly the old `ADMIN_APP_GROUPS` value.
  - `"apps"` — exactly the old `ADMIN_APPS_DISPLAY_ORDER` value.
- `ADMIN_APP_GROUPS` and `ADMIN_APPS_DISPLAY_ORDER` are **kept working, but deprecated**.
  A project can use either the old pair or the new consolidated setting, but not both at
  once (see "Backward compatibility" below) — this project is pre-1.0, but breaking
  existing projects on a minor bump isn't worth it when a deprecation path is this cheap.
  Removing the legacy settings entirely is left to a future plan once there's been a
  deprecation window (tracked as `06_remove-legacy-app-list-settings-plan`, not written yet).
- `group.py` / `reorder.py` stay pure functions taking their config as plain arguments;
  they gain one small addition (see "Accurate error messages" below) but no behavioural
  change.

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

- Missing `ADMIN_APP_LIST` entirely, and neither legacy setting present → no-op (same as
  today).
- `ADMIN_APP_LIST = {}` → no-op.
- Either inner key missing or empty → that half is skipped; the other still runs.
- Grouping still runs before ordering (unchanged composition order).
- `ADMIN_APP_LIST` not a dict, or containing a key other than `"custom_groups"` /
  `"apps"` → raises (genuine misconfiguration, e.g. a typo). Malformed *inner* values
  (e.g. `"apps"` not a dict) continue to be caught by `group_app_list` /
  `reorder_app_list` themselves, which already validate their own argument.

### Backward compatibility & deprecation

- If `ADMIN_APP_GROUPS` and/or `ADMIN_APPS_DISPLAY_ORDER` are set and `ADMIN_APP_LIST` is
  **not**, the two legacy settings are converted into the equivalent
  `{"custom_groups": ..., "apps": ...}` shape and processed exactly as if the project had
  written `ADMIN_APP_LIST` directly. A single `DeprecationWarning` is emitted pointing at
  the README migration section. (Python's default warning filter only prints a given
  warning once per call site, so this doesn't spam logs across requests.)
- If `ADMIN_APP_LIST` **and** either legacy setting are set at the same time, that's
  ambiguous configuration, not a valid transitional state — it raises
  `MalformedAppListException` rather than silently picking a winner. A project migrates
  by deleting the old settings in the same change that adds `ADMIN_APP_LIST`.
- This conversion is implemented as its own small, independently testable function
  (`resolve_app_list_setting`, in a new `legacy.py`) rather than inlined into the
  middleware, so "old settings in → new shape out (+ warning)" can be unit tested without
  spinning up the admin.

### Two usability fixes folded into this plan

These came out of reviewing the original (breaking-change) version of this plan and
apply regardless of the backward-compatibility change above:

1. **Stale error messages.** The existing `MalformedAppGroupsException` /
   `MalformedDisplayOrderException` messages hardcode the setting name they're
   validating (`"ADMIN_APP_GROUPS must be a dict..."`, etc). Once those values can
   arrive either directly (legacy settings) or indirectly (unpacked from
   `ADMIN_APP_LIST`), a hardcoded name is misleading — e.g. a project using
   `ADMIN_APP_LIST["custom_groups"]` would see an error telling it to fix
   `ADMIN_APP_GROUPS`, a setting it never wrote. Fix: give `group_app_list` /
   `reorder_app_list` an optional `setting_name` kwarg (defaulting to the legacy name, so
   no existing call site breaks), and have the middleware pass the *actual* setting the
   value came from — `"ADMIN_APP_GROUPS"` / `"ADMIN_APPS_DISPLAY_ORDER"` when resolved
   from legacy settings, or `'ADMIN_APP_LIST["custom_groups"]'` /
   `'ADMIN_APP_LIST["apps"]'` when read natively. The example snippet in each message
   always shows the new `ADMIN_APP_LIST` shape regardless of which path triggered it, so
   hitting an error under the legacy settings also nudges toward migrating.
2. **Overloaded `"apps"` key name.** `ADMIN_APP_LIST["apps"]` (ordering, keyed by real
   app label) and `ADMIN_APP_LIST["custom_groups"][group]["apps"]` (which source apps
   feed a synthetic group) use the same key name for two different concepts one nesting
   level apart. Renaming the inner one (e.g. to `"sources"`) would remove the ambiguity,
   but it would require changing `group.py`'s expected shape and the legacy-conversion
   mapping, breaking the "exactly the old `ADMIN_APP_GROUPS` value" property and touching
   a file this plan otherwise leaves alone. **Decision: don't rename it** — the
   README section for `ADMIN_APP_LIST` will show both keys in one example and call out
   explicitly that they mean different things, which is cheaper than a shape change and
   keeps `group.py` untouched.

---

## Files to Modify

| File                                    | Action                                                                 |
|------------------------------------------|-------------------------------------------------------------------------|
| `src/.../exceptions.py`                  | Add `MalformedAppListException` (incl. mixed-settings variant); add optional `setting_name` param to the two existing exceptions, defaulting to their current hardcoded name. |
| `src/.../legacy.py`                     | **New.** `resolve_app_list_setting()` — merges/validates raw `ADMIN_APP_LIST` + legacy setting values, emits the `DeprecationWarning`. |
| `src/.../group.py`                       | Accept optional `setting_name` kwarg, forward it to `MalformedAppGroupsException`. |
| `src/.../reorder.py`                     | Accept optional `setting_name` kwarg, forward it to `MalformedDisplayOrderException`. |
| `src/.../middleware.py`                 | Read all three raw settings, delegate to `resolve_app_list_setting`, pass the right `setting_name` through to `group_app_list`/`reorder_app_list`. |
| `tests/settings.py`                     | Update the module-level default to the new nested shape.               |
| `tests/test_middleware_integration.py`  | Update to set `ADMIN_APP_LIST["apps"]` instead of `ADMIN_APPS_DISPLAY_ORDER`. |
| `tests/test_group_integration.py`       | Update to set `ADMIN_APP_LIST["custom_groups"]` instead of `ADMIN_APP_GROUPS`. |
| `tests/test_middleware_settings.py`     | **New.** Unit-ish tests for the top-level `ADMIN_APP_LIST` validation. |
| `tests/test_legacy_settings.py`         | **New.** Tests for legacy-setting passthrough, the deprecation warning, and the mixed-settings error. |
| `README.md`                              | Replace the two setting sections with one; add a "Deprecated settings" note (not a hard migration deadline, since old settings keep working). |
| `pyproject.toml`                         | Bump version — minor bump (e.g. `0.9.0`), since this is additive/backward-compatible, not breaking. |

---

## Step 1 — Write failing tests for the new setting  [ STATUS: DONE ]

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

Add `tests/test_legacy_settings.py` for backward compatibility:

```python
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
    settings.ADMIN_APP_LIST = {"apps": {"auth": ["User", "Group"]}}
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
    settings.ADMIN_APP_LIST = {"apps": "not-a-dict"}
    with pytest.raises(Exception, match=r'ADMIN_APP_LIST\["apps"\]'):
        admin_client.get("/admin/")
```

These fail until `MalformedAppListException`, `legacy.py`, and the middleware changes
land.

---

## Step 2 — Add `MalformedAppListException`; make the existing two exceptions setting-name-aware  [ STATUS: DONE ]

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
```

Update the two existing exceptions to take an optional `setting_name`, defaulting to
their current hardcoded name so no existing call site needs to change:

```python
class MalformedDisplayOrderException(Exception):
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

    # for_unknown_model gets the same treatment.


class MalformedAppGroupsException(Exception):
    @classmethod
    def for_setting(cls, value, setting_name="ADMIN_APP_GROUPS"):
        ...  # same pattern

    @classmethod
    def for_group(cls, group_label, value, setting_name="ADMIN_APP_GROUPS"):
        ...

    @classmethod
    def for_app(cls, group_label, app_label, value, setting_name="ADMIN_APP_GROUPS"):
        ...
```

Note the example snippets in these two now point at `_APP_LIST_EXAMPLE` (the new,
preferred shape) rather than the old flat examples — so even an error raised from a
legacy setting nudges the user toward `ADMIN_APP_LIST`.

---

## Step 3 — Add `legacy.py` with `resolve_app_list_setting()`  [ STATUS: DONE ]

```python
import warnings

from .exceptions import MalformedAppListException

_DEPRECATION_MESSAGE = (
    "ADMIN_APP_GROUPS and ADMIN_APPS_DISPLAY_ORDER are deprecated and will be "
    "removed in a future release. Configure ADMIN_APP_LIST instead, e.g.:\n"
    '    ADMIN_APP_LIST = {"custom_groups": {...}, "apps": {...}}\n'
    "See the README's migration notes for details."
)


def resolve_app_list_setting(app_list, app_groups, apps_order):
    """Resolve the effective ADMIN_APP_LIST dict, honoring the deprecated
    ADMIN_APP_GROUPS / ADMIN_APPS_DISPLAY_ORDER settings if ADMIN_APP_LIST isn't set.

    Returns ``(setting, using_legacy)`` — ``setting`` is the dict to validate/use
    (never mutated in place), ``using_legacy`` tells the caller which setting name(s)
    to report in downstream error messages.
    """
    has_legacy = app_groups is not None or apps_order is not None

    if app_list is not None and has_legacy:
        raise MalformedAppListException.for_mixed_legacy_settings()

    if app_list is not None:
        return app_list, False

    if has_legacy:
        warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)
        return {"custom_groups": app_groups or {}, "apps": apps_order or {}}, True

    return {}, False
```

`stacklevel=3` points the warning at the settings module / call site rather than inside
this package — tune once wired into the middleware if it doesn't land right.

---

## Step 4 — Update `group.py` / `reorder.py` to accept `setting_name`  [ STATUS: DONE ]

Both files gain a `setting_name` kwarg on their public function, forwarded to whichever
exception they raise, e.g. in `reorder.py`:

```python
def reorder_app_list(app_list, apps_order, setting_name="ADMIN_APPS_DISPLAY_ORDER"):
    ...
    if not isinstance(model_order, list):
        raise MalformedDisplayOrderException.for_app(
            app["app_label"], model_order, setting_name=setting_name
        )
```

and analogously for `group_app_list` / `MalformedAppGroupsException` in `group.py`. No
other behaviour changes.

---

## Step 5 — Update `middleware.py`  [ STATUS: DONE ]

```python
from django.conf import settings

from .exceptions import MalformedAppListException
from .group import group_app_list
from .legacy import resolve_app_list_setting
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

        groups_setting_name = "ADMIN_APP_GROUPS" if using_legacy else 'ADMIN_APP_LIST["custom_groups"]'
        order_setting_name = "ADMIN_APPS_DISPLAY_ORDER" if using_legacy else 'ADMIN_APP_LIST["apps"]'

        for key in _APP_LIST_KEYS:
            value = context.get(key)
            if not isinstance(value, list):
                continue
            if app_groups:
                value = group_app_list(value, app_groups, setting_name=groups_setting_name)
            if apps_order:
                value = reorder_app_list(value, apps_order, setting_name=order_setting_name)
            context[key] = value

        return response
```

Note: `.get("custom_groups", {})` (not `.get(...) or {}`) so an explicitly-provided
non-dict value isn't silently swallowed before reaching `group_app_list`'s own
type check — except a falsy-but-wrong-type value (e.g. `"custom_groups": []`), which
is tolerated the same way an empty dict is. That's an accepted, documented edge case,
not a gap worth extra code for. This applies equally whether the dict came from
`ADMIN_APP_LIST` directly or was assembled from legacy settings by `resolve_app_list_setting`.

---

## Step 6 — Update existing tests & README  [ STATUS: DONE ]

- Sweep `tests/test_middleware_integration.py` and `tests/test_group_integration.py` for
  any remaining direct references to `ADMIN_APPS_DISPLAY_ORDER` / `ADMIN_APP_GROUPS` and
  move them under `ADMIN_APP_LIST`.
- `README.md`: replace the "Usage" and "Grouping apps under one title" sections with a
  single `ADMIN_APP_LIST` section. In that section, show both keys in one example and
  call out explicitly that `"apps"` means two different things at the two nesting
  levels (top-level ordering vs. a group's source apps) so readers aren't tripped up.
  Add a "Deprecated settings" note — not a hard-deadline migration block, since the old
  settings keep working:

  ```python
  # Still supported, but deprecated — emits a DeprecationWarning:
  ADMIN_APPS_DISPLAY_ORDER = {"auth": ["User", "Group"]}
  ADMIN_APP_GROUPS = {"content": {"apps": {"blog": ["Post"]}}}

  # Preferred:
  ADMIN_APP_LIST = {
      "apps": {"auth": ["User", "Group"]},
      "custom_groups": {"content": {"apps": {"blog": ["Post"]}}},
  }
  ```

  Note that `ADMIN_APP_LIST` cannot be combined with the deprecated settings — pick one.

Run the full suite: `poetry run python -m pytest -v` → all green.

---

## Step 7 — Version bump  [ STATUS: DONE ]

`pyproject.toml`: bump to a minor version (e.g. `0.9.0`). This is additive and
backward-compatible (old settings still work), so it doesn't need a major/breaking bump.

---

## Notes

- `group.py` and `reorder.py` get one small additive change each (`setting_name` kwarg,
  defaulted so no existing caller breaks) — everything else about them is unchanged.
- Kept `.get(key, {})` semantics (not `or {}`) to avoid masking wrong-type inner values
  with the wrong-key-name check happening first, since unknown top-level keys are a much
  more likely typo than an inner value being deliberately falsy-but-wrong-type.
- Deliberately did *not* rename the inner `custom_groups[...]["apps"]` key to disambiguate
  it from the top-level `"apps"` key — doing so would touch `group.py`'s shape and the
  legacy-conversion mapping for a naming-clarity win that's cheaper to solve in docs.
- Once there's been a reasonable deprecation window, a follow-up plan
  (`06_remove-legacy-app-list-settings-plan`) should remove `ADMIN_APP_GROUPS` /
  `ADMIN_APPS_DISPLAY_ORDER` and the `setting_name` plumbing entirely — that's a genuine
  breaking change and belongs in its own major-version release, unlike this plan.
- After each step is done, change its `[ STATUS: TODO ]` to `[ STATUS: DONE ]`.
