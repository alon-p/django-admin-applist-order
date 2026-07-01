# Plan: Uniform Ordering for Real Apps and Custom Groups (Drop Implicit Anchor)

## STATUS: DONE

## Context

Today, positioning a synthetic group (from `ADMIN_APP_LIST["custom_groups"]`) relative to
real apps is *possible* but not uniform:

- If the group's label is **not** mentioned in `ADMIN_APP_LIST["order"]`, `group_app_list`
  gives it an implicit default position: the slot of its *first present source app*
  (`group.py`'s `anchor_by_group` tracking). Real apps get a completely different implicit
  default when unlisted: alphabetical, at the end.
- If the group's label **is** mentioned in `"order"`, it's positioned explicitly, same as
  a real app.

So groups and real apps already share the *explicit* path, but have two different
*implicit* defaults. That asymmetry is the actual gap: a user has to already know about
(and remember) the anchor rule to predict where an unpositioned group lands, whereas an
unpositioned real app is trivially predictable (alphabetical).

This plan makes the implicit case uniform too: **drop the anchor**. An unpositioned group
behaves exactly like an unpositioned real app — alphabetical, at the end. The only way to
control position, for either apps or groups, is `ADMIN_APP_LIST["order"]`.

### A consequence worth calling out explicitly

`reorder_app_list` already resorts *every* app's models alphabetically whenever it runs,
unless that app has an explicit non-empty entry in `"order"` (an app absent from `"order"`
and an app with `"order": {"label": []}` are handled identically — both hit the same
`apps_order.get(label, [])` default). Two existing tests
(`test_index_app_list_has_synthetic_group`, `test_sidebar_available_apps_has_synthetic_group`
in `tests/test_group_integration.py`) currently pass `"order": {}` specifically to make
`reorder_app_list` **not run at all**, so the group's models keep the order implied by
`custom_groups`'s own `"apps": {source_app: [...]}` traversal.

Making group *positioning* uniform requires `reorder_app_list` to always run once grouping
has happened (see Step 3) — which means a group's *internal model order* also stops being
implicitly preserved, and starts defaulting to alphabetical unless pinned via `"order"`,
exactly like a real app's models. This is the correct, consistent extension of "treat
groups exactly like real apps" — not a separate decision — but it does mean the two tests
above need to explicitly pin the group's model order via `"order"` going forward if they
want to keep asserting a specific (non-alphabetical) sequence.

**Design decision (agreed with the maintainer):** ship uniform positioning *and* the model-
order consequence together, since splitting them would leave the same
"two different implicit defaults" asymmetry, just moved from position to model-order.

**Config shape (unchanged):**

```python
ADMIN_APP_LIST = {
    "custom_groups": {
        "content": {"apps": {"blog": ["Post"], "news": ["Article"]}},
    },
    "order": {
        "content": ["Post", "Article"],   # optional — without this, models are alphabetical
        "auth": [],
    },
}
```

Behaviour after this plan:

- A group not mentioned in `"order"` → alphabetical position among all apps/groups, and
  alphabetical model order within it. Identical treatment to an unmentioned real app.
- A group mentioned in `"order"` → explicit position and (if given a non-empty list)
  explicit model order — identical mechanism to a real app.
- Nothing about `custom_groups`'s own shape, validation, or model-collection behavior
  changes — only *where the group ends up*, and what its default internal model order is
  when `"order"` doesn't say otherwise.

---

## Files to Modify

| File                                    | Action                                                                 |
|------------------------------------------|-------------------------------------------------------------------------|
| `src/.../group.py`                       | Remove anchor tracking; append non-empty groups after the remaining real apps, in `custom_groups` definition order. Position is no longer this function's concern. |
| `src/.../middleware.py`                 | Always call `reorder_app_list` when grouping happened, even if `"order"` is empty — that's what makes the alphabetical default apply uniformly. |
| `tests/test_group.py`                   | Rewrite `test_group_takes_the_slot_of_its_first_source_app` for the new "appended after remaining apps" contract (no more anchor). |
| `tests/test_group_integration.py`       | Update the two tests that used `"order": {}` to skip reordering — pin the group's expected model order explicitly via `"order"` instead. |
| `README.md`                              | Update the grouping section: remove the "takes the slot of its first source app" claim; state the uniform alphabetical-by-default / explicit-via-`"order"` rule once, covering both apps and groups. |

`exceptions.py`, `legacy.py`, and `reorder.py` need **no changes** — this is entirely a
`group.py` positioning-logic removal plus a `middleware.py` call-site change.

---

## Step 1 — Write/update failing tests first  [ STATUS: DONE ]

In `tests/test_group.py`, replace the anchor test:

```python
def test_group_is_appended_after_remaining_real_apps():
    app_list = [
        make_app("auth", "Auth", "User"),
        make_app("blog", "Blog", "Post"),
        make_app("news", "News", "Article"),
        make_app("sessions", "Sessions", "Session"),
    ]
    result = group_app_list(app_list, GROUP)
    # blog and news are fully consumed and dropped; "content" is appended after
    # whatever real apps remain. Positioning relative to "auth"/"sessions" is no
    # longer group_app_list's concern — that's reorder_app_list's job now.
    assert app_labels(result) == ["auth", "sessions", "content"]
```

In `tests/test_group_integration.py`, update the two tests that relied on `"order": {}`
to skip reordering — pin the group's model order explicitly instead of relying on
`custom_groups` traversal order surviving untouched:

```python
def test_index_app_list_has_synthetic_group(admin_client, settings):
    settings.ADMIN_APP_LIST = {
        "custom_groups": ACCOUNTS_GROUP,
        "order": {"accounts": ["User", "Group", "Session"]},  # pin model order explicitly
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    assert "accounts" in labels
    assert "sessions" not in labels  # fully consumed
    assert models_of(response.context["app_list"], "accounts") == ["User", "Group", "Session"]
```

(same change for `test_sidebar_available_apps_has_synthetic_group`)

Add a new integration test proving the uniform default:

```python
def test_unpositioned_group_sorts_alphabetically_with_real_apps(admin_client, settings):
    """A group with no ``order`` entry lands alphabetically among real apps —
    the same default an unmentioned real app gets. No more implicit anchor."""
    settings.ADMIN_APP_LIST = {
        "custom_groups": {
            "zzz_group": {"apps": {"auth": ["User", "Group"]}},
        },
    }
    response = admin_client.get("/admin/")
    labels = app_labels(response.context["app_list"])
    # "zzz_group"'s display label defaults to "Zzz Group" — alphabetically last.
    assert labels[-1] == "zzz_group"
```

These fail until Steps 2–3 land.

---

## Step 2 — Simplify `group.py`: drop anchor tracking  [ STATUS: DONE ]

```python
def group_app_list(app_list, app_groups, setting_name="ADMIN_APP_GROUPS"):
    """Return a new app list with models merged into synthetic group entries.

    ...(unchanged docstring intro)...

    Rules:
      * Each ``group_label`` becomes a synthetic app whose ``app_label`` is that
        label, so it can be positioned / model-ordered via ``ADMIN_APP_LIST["order"]``
        exactly like a real app — including its *default* position when unmentioned:
        alphabetical, at the end, same as any other unlisted app. This function no
        longer picks an implicit position; it only builds the group and appends it
        after the remaining real apps. Final placement is reorder_app_list's job.
      * Listed models are moved out of their source app into the group. An empty
        list pulls all of the source app's models.
      * A source app left with no models is dropped; one with leftovers stays.
      * A group that collects no models (all sources absent) is not emitted.
      * Unknown source apps / models are skipped and logged at DEBUG, mirroring
        ``reorder_app_list``. Wrong value *types* raise MalformedAppGroupsException.
    """
    if not isinstance(app_groups, dict):
        raise MalformedAppGroupsException.for_setting(app_groups, setting_name=setting_name)

    app_by_label = {app["app_label"]: app for app in app_list}
    collected_by_group = {}   # group_label -> [model dicts], in custom_groups order

    for group_label, definition in app_groups.items():
        if not isinstance(definition, dict) or not isinstance(definition.get("apps"), dict):
            raise MalformedAppGroupsException.for_group(group_label, definition, setting_name=setting_name)

        collected = []
        for source_label, model_names in definition["apps"].items():
            if not isinstance(model_names, list):
                raise MalformedAppGroupsException.for_app(
                    group_label, source_label, model_names, setting_name=setting_name
                )
            source = app_by_label.get(source_label)
            if source is None:
                logger.debug(
                    "group %r: source app %r not found — skipping", group_label, source_label
                )
                continue
            collected.extend(_take_models(source, model_names, group_label))

        collected_by_group[group_label] = collected

    # Real apps keep their relative order; fully-consumed ones are dropped.
    # Non-empty groups are appended after, in custom_groups definition order.
    # Where everything ends up is reorder_app_list's job, not this function's.
    result = [app for app in app_list if app["models"]]
    for group_label, collected in collected_by_group.items():
        if collected:
            result.append(
                _make_group(group_label, app_groups[group_label].get("display_label"), collected)
            )

    return result
```

`_take_models` and `_make_group` are unchanged. `anchor_by_group` and the "insert at
anchor's slot" rebuild loop are deleted entirely — this is a net simplification.

---

## Step 3 — Update `middleware.py`: always reorder once grouping ran  [ STATUS: DONE ]

```python
for key in _APP_LIST_KEYS:
    value = context.get(key)
    if not isinstance(value, list):
        continue
    if app_groups:
        value = group_app_list(value, app_groups, setting_name=groups_setting_name)
    if app_groups or apps_order:
        value = reorder_app_list(value, apps_order, setting_name=order_setting_name)
    context[key] = value
```

The only change from today is `if apps_order:` → `if app_groups or apps_order:`. When only
`apps_order` is set, behavior is identical to before. When `app_groups` is set (with or
without `apps_order`), `reorder_app_list` now always runs — with `apps_order` defaulting
to `{}` if the user didn't set `"order"` — which is exactly what makes the alphabetical
default apply uniformly to groups and real apps alike.

---

## Step 4 — Update README  [ STATUS: DONE ]

In the "Grouping" section, replace:

> The group takes the slot of its first source app. Because its `app_label` is the key
> (`"content"`), you can position it and order its models with `ADMIN_APP_LIST["order"]`
> just like a real app.

with something that states the uniform rule once, e.g.:

> A group's `app_label` is its key (`"content"`), so `ADMIN_APP_LIST["order"]` treats it
> exactly like a real app: mention it there to position it and/or order its models;
> leave it out and it falls back to the same default an unmentioned real app gets —
> alphabetical, at the end.

Run the full suite: `poetry run python -m pytest -v` → all green.

---

## Notes

- No exception, settings-shape, or `reorder.py` changes — this plan is scoped entirely to
  `group.py`'s positioning logic and one `middleware.py` call-site guard.
- Version bump left to the maintainer's judgment/release process, not prescribed here.
- After each step is done, change its `[ STATUS: TODO ]` to `[ STATUS: DONE ]`.
