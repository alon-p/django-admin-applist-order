# Plan: Add integration tests

## Goal

The current suite (`tests/test_reorder.py`) only exercises the pure `reorder.py` logic
with hand-built dicts. That proves the algorithm is correct, but it does **not** prove
that wiring `AppListOrderMiddleware` into a real Django stack actually changes what the
admin renders.

These integration tests close that gap: spin up a **real Django admin**, hit the admin
index and sidebar through Django's test client, and assert that the order of apps/models
in the response context is the one we configured via `ADMIN_APPS_DISPLAY_ORDER` — and
that it differs from Django's default order (so we know the middleware, not Django, did it).

---

## Status

| Step | Description | Owner | Status |
|------|-------------|-------|--------|
| 1 | `tests/settings.py`: grow to a renderable admin | Claude | ☐ Not started |
| 2 | `tests/urls.py`: admin URLs + extra registered models | Claude | ☐ Not started |
| 3 | `tests/test_middleware_integration.py`: drive the real admin | Claude | ☐ Not started |
| 4 | Optional hardening (only if cheap) | Claude | ☐ Not started |
| 5 | Run the suite | User | ☐ Not started |

**Principle: use as little of Django as necessary.** No project scaffolding, no custom
models, no migrations of our own. We reuse models that ship with `contrib` apps and
register them on the admin site purely to populate the app list.

---

## What "as little Django as necessary" means here

To render `/admin/` Django needs, at minimum:

| Need | Why | Minimal choice |
|------|-----|----------------|
| Admin + auth + contenttypes + sessions apps | admin index requires them | already mostly in `tests/settings.py` |
| `MIDDLEWARE` | sessions/auth/messages + **our middleware** | add to settings |
| `TEMPLATES` with admin context processors | admin templates render | add a single `DjangoTemplates` backend |
| `ROOT_URLCONF` | `/admin/` must resolve | tiny `tests/urls.py` |
| A logged-in superuser | admin index is login-gated | pytest-django `admin_client` fixture (needs DB) |
| ≥ 2 admin apps with ≥ 2 models | so ordering is observable | register existing contrib models (`ContentType`, `Session`) — **no new models written** |

The only "real" thing we add is registering a couple of already-existing models so the
admin index has more than one app to reorder.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `tests/settings.py` | Add `MIDDLEWARE`, `TEMPLATES`, `ROOT_URLCONF`, `sessions`/`messages` apps, and `ADMIN_APPS_DISPLAY_ORDER` |
| `tests/urls.py` | New — expose `admin.site.urls` and register extra contrib models in admin |
| `tests/test_middleware_integration.py` | New — drive `/admin/` with the test client and assert ordering |

---

## Step 1 — `tests/settings.py`: grow to a renderable admin

Extend the existing minimal settings (keep what's there, add the rest):

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
SECRET_KEY = "test-secret-key"

ROOT_URLCONF = "tests.urls"

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # The middleware under test:
    "django_admin_applist_order.middleware.AppListOrderMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
        },
    },
]

# Deliberately NOT alphabetical, so a passing test can only mean the
# middleware reordered things (not Django's default sort).
ADMIN_APPS_DISPLAY_ORDER = {
    "sessions": [],          # app listed first, models alpha-sorted
    "auth": ["Group", "User"],  # force Group before User (default is User, Group)
}
```

Notes:
- `ADMIN_APPS_DISPLAY_ORDER` is read at request time via `getattr(settings, ...)`, so
  individual tests can still override it with pytest-django's `settings` fixture.
- We could instead expose the setting per-test only, but baking a sane default keeps the
  settings module self-describing.

---

## Step 2 — `tests/urls.py`: admin URLs + extra registered models

We register **already-existing** contrib models so the admin index has multiple apps
without us defining/migrating any model of our own.

```python
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.urls import path

# Give the admin index more than one app to reorder. auth already
# registers User + Group; these add the `contenttypes` and `sessions` apps.
admin.site.register(ContentType)
admin.site.register(Session)

urlpatterns = [path("admin/", admin.site.urls)]
```

After this the admin index has apps: `auth` (User, Group), `contenttypes` (ContentType),
`sessions` (Session) — enough to assert both **app** order and **within-app model** order.

---

## Step 3 — `tests/test_middleware_integration.py`: drive the real admin

Use pytest-django's `admin_client` (a `Client` already logged in as a superuser) and the
`db` it implies. Read the **rendered response context** — that's the exact structure the
middleware mutates.

```python
import pytest

pytestmark = pytest.mark.django_db


def app_labels(app_list):
    return [app["app_label"] for app in app_list]


def model_names(app_list, app_label):
    app = next(a for a in app_list if a["app_label"] == app_label)
    return [m["object_name"] for m in app["models"]]


def test_index_app_list_is_reordered(admin_client):
    """The admin index `app_list` follows ADMIN_APPS_DISPLAY_ORDER."""
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])

    # Listed apps first, in mapping order; unlisted (contenttypes) after, alpha.
    assert labels.index("sessions") < labels.index("auth")
    assert labels.index("auth") < labels.index("contenttypes")


def test_within_app_model_order_is_applied(admin_client):
    """Models inside `auth` follow the per-app order (Group before User)."""
    response = admin_client.get("/admin/")
    assert model_names(response.context["app_list"], "auth") == ["Group", "User"]


def test_sidebar_available_apps_is_reordered(admin_client):
    """The nav sidebar uses `available_apps`; it must be reordered too."""
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["available_apps"])
    assert labels.index("sessions") < labels.index("auth")


def test_default_order_differs_without_setting(admin_client, settings):
    """Sanity check: with the setting empty, order is Django's default,
    proving our other assertions are caused by the middleware."""
    settings.ADMIN_APPS_DISPLAY_ORDER = {}
    response = admin_client.get("/admin/")
    # Django's default within-app order for auth is User, then Group.
    assert model_names(response.context["app_list"], "auth") == ["User", "Group"]
```

### Why this proves the middleware works
- The assertions read `response.context["app_list"]` / `["available_apps"]` — the very
  keys the middleware rewrites in `process_template_response`. If the middleware were
  removed from `MIDDLEWARE`, the configured order would not appear.
- `test_default_order_differs_without_setting` pins the *contrast*: empty setting →
  Django's native order. Combined with the positive tests, a green suite means the
  ordering change is attributable to the middleware + setting, not to Django.

---

## Step 4 — Optional hardening (only if cheap)

- **Negative/no-op control:** a test that flips the middleware off (via
  `settings.MIDDLEWARE` without our class) and asserts the default order — makes the
  "middleware caused it" claim airtight. Skip if it adds noise; Step 3's contrast test
  mostly covers it.
- **HTML smoke check:** assert `response.status_code == 200` and that the rendered
  `response.content` lists the apps in the expected sequence (catches template-level
  regressions, not just context). Lower value, higher brittleness — leave out unless a
  context-only test ever proves insufficient.

---

## Step 5 — Run (user-run, not Claude)

> **This step is performed by the user, not Claude.** Claude completes Steps 1–4 (writing
> the settings, URLs, and tests); the user runs the suite locally to confirm it passes.

What needs to be done:

1. Ensure dev dependencies are installed: `pip install . --group dev`
   (`pytest` + `pytest-django` are already in the dev group).
2. Run just the new integration tests:
   `poetry run python -m pytest tests/test_middleware_integration.py -v`
3. Run the full suite (unit + integration):
   `poetry run python -m pytest`

No config or dependency changes are needed: `DJANGO_SETTINGS_MODULE = "tests.settings"` is
already set in `pyproject.toml`, and `pytest-django` is already a dev dependency.

---

## Summary of the approach

| Layer | Existing (unit) | Added (integration) |
|-------|-----------------|----------------------|
| Target | `reorder_app_list` / `_order_models` | `AppListOrderMiddleware` in a live stack |
| Input | hand-built dicts | real admin-rendered context |
| Django used | none | admin + auth/contenttypes/sessions/messages, test client, in-memory sqlite |
| Proves | algorithm is correct | wiring it in actually reorders the admin views |

The two suites are complementary: unit tests stay fast and exhaustive on edge cases;
integration tests give one honest end-to-end guarantee with the smallest viable slice of
Django.