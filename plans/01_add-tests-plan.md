# Plan: Add pytest tests

# STATUS: DONE

## Context

The package has two testable modules — `reorder.py` (pure Python, no Django) and `middleware.py` (needs minimal Django
settings). The `tests/` directory exists but is empty. CI already runs `python -m pytest`, so tests just need to be
written and dependencies added.

---

## Files to Create / Modify

| File                       | Action                                                                        |
|----------------------------|-------------------------------------------------------------------------------|
| `pyproject.toml`           | Add `[dependency-groups] dev` with `pytest` and `pytest-django`               |
| `tests/settings.py`        | Minimal Django settings module for tests                                      |
| `tests/test_reorder.py`    | Unit tests for `reorder.py` (no Django needed)                                |
| `tests/test_middleware.py` | Tests for `AppListOrderMiddleware` using `pytest-django`'s `settings` fixture |

---

## Step 1 — `pyproject.toml`: add dev dependency group and pytest config

```toml
[dependency-groups]
dev = ["pytest", "pytest-django"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
```

---

## Step 2 — `tests/settings.py`: minimal Django settings module

```python
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
SECRET_KEY = "test-secret-key"
```

---

## Step 3 — `tests/test_reorder.py`: pure unit tests (no Django)

Test `reorder_app_list` and `_order_models` (via `reorder_app_list`) with plain dicts.

**Cases:**

- Empty app list → `[]`
- Empty `apps_order` → apps sorted alphabetically by display name (case-insensitive)
- All apps listed → returned in `apps_order` dict order
- Mix: listed apps first, unlisted alphabetically after
- App in `apps_order` missing from `app_list` → silently ignored
- Empty model list `[]` for an app → all models sorted alphabetically
- Mix of listed/unlisted models → listed first, unlisted alphabetically
- Missing model name in `model_order` → skipped (verify warning logged)
- Case-insensitive model name matching (e.g. `"post"` matches `object_name="Post"`)

---

## Step 4 — `tests/test_middleware.py`: middleware tests

Use `MagicMock` for request/response objects and the `pytest-django` `settings` fixture to control
`ADMIN_APPS_DISPLAY_ORDER`.

**Cases:**

- `__call__` passes through to `get_response`
- `process_template_response`: setting missing → response unchanged
- `process_template_response`: setting empty dict → response unchanged (falsy)
- `process_template_response`: `context_data` is `None` → response unchanged
- `process_template_response`: context has `app_list` → list is reordered
- `process_template_response`: context has `available_apps` → list is reordered
- `process_template_response`: context value is not a list → left unchanged
- Both `app_list` and `available_apps` present → both reordered independently

---

## Helper

`make_app` helper used across both test files:

```python
def make_app(app_label, name, *model_names):
    return {
        "app_label": app_label,
        "name": name,
        "models": [{"object_name": m, "name": m} for m in model_names],
    }
```

---

## Verification

```bash
poetry install --with dev
poetry run python -m pytest -v

# Single file:
poetry run python -m pytest tests/test_reorder.py -v
```
