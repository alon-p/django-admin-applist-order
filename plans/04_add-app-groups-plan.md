# Plan: Group Models From Multiple Apps Under One Sidebar Title

## STATUS: TODO

## Context

`ADMIN_APPS_DISPLAY_ORDER` only **reorders** apps and the models within them. Django's admin
sidebar always groups models by the app they belong to, so there is no way to show, say, a
single **"Content"** heading containing `Post` (from the `blog` app) and
`Article` (from the `news` app).

This plan adds a second, composable setting — `ADMIN_APP_GROUPS` — that merges models from
several real apps into a **synthetic** app entry. It reuses the same mechanism the package
already relies on: post-processing the `app_list` / `available_apps` lists Django puts in the
admin response context. No `AdminSite` swap, no admin-registration changes.

**Design decisions (already agreed with the maintainer):**

- **Group replaces entries.** Grouped models are *moved out* of their source apps. A source app
  left with no models disappears from the sidebar; one with leftover models stays.
- **Composes with ordering.** Grouping runs **first** and produces a synthetic app whose
  `app_label` is the group's key. That key can then be used in `ADMIN_APPS_DISPLAY_ORDER` to
  position the group and order the models inside it — exactly like a real app.
- **Same tolerance as `reorder.py`.** Unknown source apps / models are skipped and logged at
  DEBUG (permission-dependent, not a misconfiguration). Wrong *types* raise.

**Config shape:**

```python
ADMIN_APP_GROUPS = {
    "content": {                       # synthetic app_label (use this in ADMIN_APPS_DISPLAY_ORDER)
        "name": "Content",             # sidebar title (optional; defaults to key.title())
        "apps": {                       # source app_label -> models to pull in ([] = all models)
            "blog": ["Post"],
            "news": ["Article"],
        },
    },
}
```

---

## Files to Modify

| File                                         | Action                                                              |
|----------------------------------------------|---------------------------------------------------------------------|
| `src/.../group.py`                           | **New.** Pure, framework-free grouping logic (`group_app_list`).    |
| `src/.../exceptions.py`                       | Add `MalformedAppGroupsException` (mirrors the ordering one).       |
| `src/.../middleware.py`                       | Run grouping before reorder; fire when *either* setting is present. |
| `tests/test_group.py`                        | **New.** Red→green unit tests for `group_app_list`.                 |
| `tests/test_group_integration.py`           | **New.** Integration tests through `/admin/`.                       |
| `README.md`                                  | Document `ADMIN_APP_GROUPS`.                                         |
| `pyproject.toml`                             | Bump `version` `0.7.0` → `0.8.0`.                                    |

---

## Step 1 — Write the failing (red) unit tests  [ STATUS: TODO ]

Create `tests/test_group.py`. Reuse the same tiny dict-builder style as `test_reorder.py`.
Note the group model dicts need an `admin_url` (real Django model dicts have one), so the helper
adds it.

```python
import logging

import pytest

from django_admin_applist_order.exceptions import MalformedAppGroupsException
from django_admin_applist_order.group import group_app_list


def make_app(app_label, name, *model_names):
    return {
        "app_label": app_label,
        "name": name,
        "app_url": f"/admin/{app_label}/",
        "has_module_perms": True,
        "models": [
            {"object_name": m, "name": m, "admin_url": f"/admin/{app_label}/{m.lower()}/"}
            for m in model_names
        ],
    }


def app_labels(app_list):
    return [a["app_label"] for a in app_list]


def app_by_label(app_list, label):
    return next(a for a in app_list if a["app_label"] == label)


def model_object_names(app):
    return [m["object_name"] for m in app["models"]]


GROUP = {
    "content": {
        "name": "Content",
        "apps": {"blog": ["Post"], "news": ["Article"]},
    },
}


def test_group_merges_models_from_multiple_apps():
    app_list = [
        make_app("blog", "Blog", "Post"),
        make_app("news", "News", "Article"),
    ]
    result = group_app_list(app_list, GROUP)
    group = app_by_label(result, "content")
    assert group["name"] == "Content"
    assert model_object_names(group) == ["Post", "Article"]


def test_fully_consumed_source_apps_are_dropped():
    app_list = [
        make_app("blog", "Blog", "Post"),
        make_app("news", "News", "Article"),
    ]
    result = group_app_list(app_list, GROUP)
    assert app_labels(result) == ["content"]  # both source apps emptied and dropped


def test_partial_source_app_keeps_its_leftover_models():
    app_list = [
        make_app("blog", "Blog", "Post", "Author"),
        make_app("news", "News", "Article"),
    ]
    result = group_app_list(app_list, GROUP)
    blog = app_by_label(result, "blog")
    assert model_object_names(blog) == ["Author"]  # leftover stays
    assert model_object_names(app_by_label(result, "content")) == [
        "Post",
        "Article",
    ]


def test_empty_model_list_pulls_all_models_of_that_app():
    app_list = [make_app("blog", "Blog", "Post", "Author")]
    result = group_app_list(app_list, {"content": {"apps": {"blog": []}}})
    assert model_object_names(app_by_label(result, "content")) == [
        "Post",
        "Author",
    ]
    assert "blog" not in app_labels(result)


def test_name_defaults_to_titleized_key():
    app_list = [make_app("news", "News", "Article")]
    result = group_app_list(app_list, {"content": {"apps": {"news": ["Article"]}}})
    assert app_by_label(result, "content")["name"] == "Content"


def test_group_takes_the_slot_of_its_first_source_app():
    app_list = [
        make_app("auth", "Auth", "User"),
        make_app("blog", "Blog", "Post"),
        make_app("news", "News", "Article"),
        make_app("sessions", "Sessions", "Session"),
    ]
    result = group_app_list(app_list, GROUP)
    # "content" replaces the blog slot; news is consumed & dropped.
    assert app_labels(result) == ["auth", "content", "sessions"]


def test_group_url_points_at_first_collected_model():
    app_list = [
        make_app("blog", "Blog", "Post"),
        make_app("news", "News", "Article"),
    ]
    result = group_app_list(app_list, GROUP)
    group = app_by_label(result, "content")
    assert group["app_url"] == "/admin/blog/post/"


def test_missing_source_app_is_skipped_and_logs(caplog):
    app_list = [make_app("news", "News", "Article")]
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.group"):
        result = group_app_list(app_list, GROUP)  # blog absent
    group = app_by_label(result, "content")
    assert model_object_names(group) == ["Article"]
    assert any("blog" in r.message.lower() for r in caplog.records)


def test_unknown_model_is_skipped_and_logs(caplog):
    app_list = [make_app("news", "News", "Article")]
    cfg = {"content": {"apps": {"news": ["Ghost", "Article"]}}}
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.group"):
        result = group_app_list(app_list, cfg)
    assert model_object_names(app_by_label(result, "content")) == ["Article"]
    assert any("ghost" in r.message.lower() for r in caplog.records)


def test_group_with_no_collected_models_is_not_emitted():
    app_list = [make_app("auth", "Auth", "User")]
    result = group_app_list(app_list, GROUP)  # neither source app present
    assert app_labels(result) == ["auth"]  # no empty "content" entry


def test_setting_not_a_dict_raises():
    with pytest.raises(MalformedAppGroupsException):
        group_app_list([], ["content"])


def test_group_value_not_a_dict_raises():
    with pytest.raises(MalformedAppGroupsException):
        group_app_list([], {"content": ["blog"]})


def test_model_list_not_a_list_raises():
    with pytest.raises(MalformedAppGroupsException):
        group_app_list([], {"content": {"apps": {"news": "Article"}}})
```

These fail because `group.py` / the exception do not exist yet.

---

## Step 2 — Add `MalformedAppGroupsException`  [ STATUS: TODO ]

In `src/django_admin_applist_order/exceptions.py`, add a parallel exception. Keep the same
classmethod-constructor style as `MalformedDisplayOrderException`.

```python
_GROUP_EXAMPLE = (
    "    ADMIN_APP_GROUPS = {\n"
    '        "content": {\n'
    '            "name": "Content",\n'
    '            "apps": {"blog": ["Post"], "news": ["Article"]},\n'
    "        }\n"
    "    }"
)


class MalformedAppGroupsException(Exception):
    """Raised when ADMIN_APP_GROUPS is not structured correctly.

    The setting must be a dict mapping a synthetic app label (str) to a group
    definition: a dict with an ``"apps"`` mapping of ``{app_label: [model, ...]}``
    and an optional ``"name"`` display title.
    """

    @classmethod
    def for_setting(cls, value):
        return cls(
            f"ADMIN_APP_GROUPS must be a dict mapping group labels to group "
            f"definitions, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_GROUP_EXAMPLE}"
        )

    @classmethod
    def for_group(cls, group_label, value):
        return cls(
            f"ADMIN_APP_GROUPS[{group_label!r}] must be a dict with an 'apps' mapping, "
            f"got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_GROUP_EXAMPLE}"
        )

    @classmethod
    def for_app(cls, group_label, app_label, value):
        return cls(
            f"ADMIN_APP_GROUPS[{group_label!r}]['apps'][{app_label!r}] must be a list of "
            f"model names, got {type(value).__name__}: {value!r}.\n"
            f"Example:\n{_GROUP_EXAMPLE}"
        )
```

---

## Step 3 — Implement `group.py`  [ STATUS: TODO ]

Create `src/django_admin_applist_order/group.py`. Pure functions on the list-of-dicts, mirroring
`reorder.py`'s framing.

```python
"""Merge models from several apps into synthetic sidebar groups.

Framework-free, mirroring ``reorder.py``: operates on the plain list-of-dicts
structure Django builds for the admin index and nav sidebar. Each app dict has
``app_label``, ``name``, ``app_url`` and ``models``; each model dict has
``object_name``, ``name`` and ``admin_url``.
"""

import logging

from .exceptions import MalformedAppGroupsException

logger = logging.getLogger(__name__)


def group_app_list(app_list, app_groups):
    """Return a new app list with models merged into synthetic group entries.

    ``app_groups`` is the ADMIN_APP_GROUPS mapping::

        {group_label: {"name": "Title", "apps": {app_label: [ModelName, ...]}}}

    Rules:
      * Each ``group_label`` becomes a synthetic app whose ``app_label`` is that
        label, so it can be positioned / model-ordered via
        ADMIN_APPS_DISPLAY_ORDER exactly like a real app.
      * Listed models are moved out of their source app into the group. An empty
        list pulls all of the source app's models.
      * A source app left with no models is dropped; one with leftovers stays.
      * The group takes the slot of its first present source app. A group that
        collects no models (all sources absent) is not emitted.
      * Unknown source apps / models are skipped and logged at DEBUG, mirroring
        ``reorder_app_list``. Wrong value *types* raise MalformedAppGroupsException.
    """
    if not isinstance(app_groups, dict):
        raise MalformedAppGroupsException.for_setting(app_groups)

    app_by_label = {app["app_label"]: app for app in app_list}
    collected_by_group = {}   # group_label -> [model dicts]
    anchor_by_group = {}      # group_label -> app_label its slot should replace

    for group_label, definition in app_groups.items():
        if not isinstance(definition, dict) or not isinstance(definition.get("apps"), dict):
            raise MalformedAppGroupsException.for_group(group_label, definition)

        collected = []
        anchor = None
        for source_label, model_names in definition["apps"].items():
            if not isinstance(model_names, list):
                raise MalformedAppGroupsException.for_app(group_label, source_label, model_names)
            source = app_by_label.get(source_label)
            if source is None:
                logger.debug(
                    "group %r: source app %r not found — skipping", group_label, source_label
                )
                continue
            if anchor is None:
                anchor = source_label
            collected.extend(_take_models(source, model_names, group_label))

        collected_by_group[group_label] = collected
        anchor_by_group[group_label] = anchor

    # Rebuild: insert each non-empty group at its anchor app's slot; drop apps
    # that were fully consumed.
    result = []
    inserted = set()
    for app in app_list:
        for group_label, anchor in anchor_by_group.items():
            if (
                anchor == app["app_label"]
                and group_label not in inserted
                and collected_by_group[group_label]
            ):
                result.append(
                    _make_group(
                        group_label,
                        app_groups[group_label].get("name"),
                        collected_by_group[group_label],
                    )
                )
                inserted.add(group_label)
        if app["models"]:
            result.append(app)

    return result


def _take_models(app, model_names, group_label):
    """Remove and return the requested models from ``app`` in place.

    Empty ``model_names`` takes all models. Unknown names are skipped + logged.
    Returned models preserve the order given in ``model_names``.
    """
    if not model_names:
        taken = app["models"]
        app["models"] = []
        return taken

    by_name = {m["object_name"].lower(): m for m in app["models"]}
    taken = []
    for name in model_names:
        model = by_name.get(name.lower())
        if model is None:
            logger.debug(
                "group %r: model %r not found in app %r — skipping",
                group_label, name, app["app_label"],
            )
            continue
        taken.append(model)

    taken_ids = {id(m) for m in taken}
    app["models"] = [m for m in app["models"] if id(m) not in taken_ids]
    return taken


def _make_group(group_label, name, models):
    """Build a synthetic app dict shaped like the ones Django produces."""
    return {
        "name": name or group_label.replace("_", " ").title(),
        "app_label": group_label,
        # No dedicated index page for a synthetic group; land on the first model.
        # (Simpler than overriding admin templates to render a link-less title.)
        "app_url": models[0].get("admin_url", "") if models else "",
        "has_module_perms": True,
        "models": models,
    }
```

Run: `poetry run python -m pytest tests/test_group.py -v` → all green.

---

## Step 4 — Wire grouping into the middleware  [ STATUS: TODO ]

Grouping must run even when `ADMIN_APPS_DISPLAY_ORDER` is unset, and must run **before** reorder
so the synthetic label can be positioned. Update `middleware.py`:

```python
from django.conf import settings

from .exceptions import MalformedDisplayOrderException
from .group import group_app_list
from .reorder import reorder_app_list
import logging

_APP_LIST_KEYS = ("app_list", "available_apps")

logger = logging.getLogger(__name__)


class AppListOrderMiddleware:
    """Group and/or reorder the admin app list from settings.

    - ``ADMIN_APP_GROUPS`` merges models from several apps into synthetic groups.
    - ``ADMIN_APPS_DISPLAY_ORDER`` orders apps and the models within them.

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
```

(`group_app_list` validates the `ADMIN_APP_GROUPS` type itself, so no extra guard is needed here.)

---

## Step 5 — Integration tests  [ STATUS: TODO ]

Create `tests/test_group_integration.py`. The test settings only install
`admin/auth/contenttypes/sessions/messages`, so group real built-in models to prove the
end-to-end path (index `app_list` **and** sidebar `available_apps`).

```python
import pytest

pytestmark = pytest.mark.django_db


def app_labels(app_list):
    return [a["app_label"] for a in app_list]


def models_of(app_list, label):
    app = next(a for a in app_list if a["app_label"] == label)
    return [m["object_name"] for m in app["models"]]


ACCOUNTS_GROUP = {
    "accounts": {
        "name": "Accounts",
        "apps": {"auth": ["User", "Group"], "sessions": ["Session"]},
    }
}


def test_index_app_list_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert "accounts" in labels
    assert "sessions" not in labels  # fully consumed
    assert models_of(response.context["app_list"], "accounts") == ["User", "Group", "Session"]


def test_sidebar_available_apps_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    response = admin_client.get("/admin/")
    assert "accounts" in app_labels(response.context["available_apps"])


def test_grouping_composes_with_ordering(admin_client, settings):
    """The synthetic label can be positioned and its models ordered via
    ADMIN_APPS_DISPLAY_ORDER."""
    settings.ADMIN_APP_GROUPS = ACCOUNTS_GROUP
    settings.ADMIN_APPS_DISPLAY_ORDER = {
        "accounts": ["Session", "User", "Group"],  # reorder within the group
        "contenttypes": [],
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert labels[0] == "accounts"  # positioned first
    assert models_of(response.context["app_list"], "accounts") == ["Session", "User", "Group"]


def test_no_group_setting_is_a_noop(admin_client, settings):
    settings.ADMIN_APP_GROUPS = {}
    response = admin_client.get("/admin/")
    assert "accounts" not in app_labels(response.context["app_list"])
```

Run the full suite: `poetry run python -m pytest -v` → all green.

---

## Step 6 — Document in README  [ STATUS: TODO ]

Add a section after the `ADMIN_APPS_DISPLAY_ORDER` usage:

````markdown
## Grouping apps under one title (`ADMIN_APP_GROUPS`)

Merge models from several apps into a single sidebar heading:

```python
ADMIN_APP_GROUPS = {
    "content": {                       # synthetic app label
        "name": "Content",             # sidebar title (optional; defaults to the key, title-cased)
        "apps": {                       # source app label -> models to pull in ([] = all models)
            "blog": ["Post"],
            "news": ["Article"],
        },
    },
}
```

Behaviour:

- Grouped models are **moved out** of their source apps. A source app left with no models
  disappears; one with leftover models stays.
- The group takes the slot of its first source app. Because its `app_label` is the key
  (`"content"`), you can position it and order its models with `ADMIN_APPS_DISPLAY_ORDER`
  just like a real app:

  ```python
  ADMIN_APPS_DISPLAY_ORDER = {
      "content": ["Post", "Article"],  # order within the group
      # ... other apps
  }
  ```

- Unknown source apps or models (e.g. not visible to the current user) are skipped silently.
- If the setting is missing or empty, nothing changes.
````

Also mention `ADMIN_APP_GROUPS` in the intro/"How it works" sections alongside the ordering
setting.

---

## Step 7 — Version bump  [ STATUS: TODO ]

`pyproject.toml`: `version = "0.7.0"` → `version = "0.8.0"` (new backward-compatible feature).
Update the `description` if desired to mention grouping.

---

## Step 8 — Release  [ STATUS: TODO ]

After merge, publish 0.8.0 to PyPI. Downstream projects can then bump the dependency, add an
`ADMIN_APP_GROUPS` setting, and optionally position the group via `ADMIN_APPS_DISPLAY_ORDER`.

---

## Notes

- **Composition order matters:** group first, then reorder. Reversing them would order apps that
  are about to be dissolved into a group.
- **DEBUG logging** for skipped apps/models is intentional and consistent with `reorder.py`:
  low-privilege users legitimately don't see every model.
- The synthetic group's `app_url` points at its first model's changelist because a cross-app
  group has no real app-index page. This keeps the heading clickable and lands somewhere sane,
  and avoids having to override admin templates to render a link-less title.
- `MalformedAppGroupsException` only fires for wrong *types* (a genuine misconfiguration), never
  for missing apps/models (a permission situation).
- After each step is done, change its `[ STATUS: TODO ]` to `[ STATUS: DONE ]`.
```
