# Plan: Skip Unknown Models/Apps Instead of Raising

## STATUS: TODO

## Context

`reorder.py` currently raises `MalformedDisplayOrderException` when a model listed in
`ADMIN_APPS_DISPLAY_ORDER` is not found in the live app list. This is too strict: different
users have different admin permissions, so a model that exists in code may simply not be
visible to the current user. Raising an error in that case breaks their admin view entirely.

The same silent-skip behavior already exists at the **app** level (line 27 of `reorder.py`):
apps in the config but missing from the live list are already silently ignored. Models should
behave the same way, but currently do not.

**Goal:** Replace the raise in `_order_models` with a `logger.debug(...)` + skip. Also add a
debug log for the already-silent app-level skip so all skips are observable when debugging.

---

## Files to Modify

| File                          | Action                                                           |
|-------------------------------|------------------------------------------------------------------|
| `src/.../reorder.py`          | Add logger, replace raise with debug log + skip; log app skips  |
| `tests/test_reorder.py`       | Add red→green tests for new skip behavior                        |

---

## Step 1 — Write the failing (red) tests  [ STATUS: DONE ]

Add new test cases to `tests/test_reorder.py` that describe the desired behavior.
These tests will **fail** against the current code, confirming they are testing the right thing.

### Test: unknown model in config is skipped, not an error

```python
def test_unknown_model_in_order_is_skipped_not_an_error():
    # Model "Ghost" is in the config but not visible to this user.
    # The reordering should succeed and just omit "Ghost" from the result.
    app = make_app("blog", "Blog", "Post", "Author")
    result = reorder_app_list([app], {"blog": ["Ghost", "Post"]})
    # "Ghost" is skipped; "Post" is first (listed), "Author" follows (unlisted, alphabetical)
    assert model_object_names(result[0]) == ["Post", "Author"]
```

### Test: unknown model skip emits a debug log

```python
def test_unknown_model_in_order_logs_at_debug(caplog):
    import logging
    app = make_app("blog", "Blog", "Post", "Author")
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.reorder"):
        reorder_app_list([app], {"blog": ["Ghost", "Post"]})
    assert any("ghost" in record.message.lower() for record in caplog.records)
    assert any("blog" in record.message.lower() for record in caplog.records)
```

### Test: unknown app in config is skipped and logs at debug

```python
def test_unknown_app_in_order_logs_at_debug(caplog):
    import logging
    app_list = [make_app("auth", "Auth", "User")]
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.reorder"):
        reorder_app_list(app_list, {"ghost_app": [], "auth": []})
    assert any("ghost_app" in record.message.lower() for record in caplog.records)
```

### Update the existing raise test to assert the *new* behavior

The test `test_unknown_model_in_order_raises` now documents the **old** behavior. Replace it:

```python
# REMOVE: test_unknown_model_in_order_raises (old behavior — now a skip, not a raise)

# KEEP the new tests above instead
```

---

## Step 2 — Implement the change in `reorder.py`  [ STATUS: DONE ]

### 2a — Add a logger (reorder.py has none today)

```python
import logging

logger = logging.getLogger(__name__)
```

### 2b — In `reorder_app_list`: log skipped apps

After the existing line that silently filters missing apps, add a debug log:

```python
listed_labels = [label for label in apps_order if label in app_dict]
for label in apps_order:
    if label not in app_dict:
        logger.debug("app %r not found in admin app list — skipping", label)
```

### 2c — In `_order_models`: replace raise with debug log + skip

```python
# Before:
if model is None:
    raise MalformedDisplayOrderException.for_unknown_model(
        app["app_label"], name, [m["object_name"] for m in app["models"]]
    )
listed.append(model)

# After:
if model is None:
    logger.debug("app %r: model %r not found — skipping", app["app_label"], name)
    continue
listed.append(model)
```

---

## Step 3 — Run the tests (green)  [ STATUS: DONE ]

```bash
poetry run python -m pytest tests/test_reorder.py -v
```

All tests should pass, including the new ones. The old `test_unknown_model_in_order_raises`
test must be gone (it tested the removed behavior).

---

## Step 4 — Verify nothing else broke  [ STATUS: TODO ]

```bash
poetry run python -m pytest -v
```

Full suite green. The `MalformedDisplayOrderException.for_unknown_model` classmethod can stay
(it is still used by nothing, but removing it is a separate cleanup task).

---

## Notes

- The log level is **DEBUG** intentionally: in a multi-tenant site every page load may skip
  several models for low-privilege users, so INFO or WARNING would be too noisy.
- `MalformedDisplayOrderException.for_setting` and `for_app` (malformed *value* types) still
  raise — those are genuine misconfigurations, not permission issues.
- After each step is done, change its `[ STATUS: TODO ]` to `[ STATUS: DONE ]`.