# django-admin-applist-order

> A simple Django middleware to reorder and group the admin app list from settings in `settings.py`.

Order the Django admin **app list** — the apps shown on the admin index, and
the models within each app — from a single dict in your `settings.py`. You can
also merge models from several apps under one synthetic sidebar heading.

It works through a middleware that post-processes the admin's response, so you
**don't** need to swap your `AdminSite` or change any admin registration. Add
one line to `MIDDLEWARE`, define the setting, done.

## Quickstart

```python
MIDDLEWARE = [
    # ...
    "django_admin_applist_order.middleware.AppListOrderMiddleware",
]

ADMIN_APP_LIST = {
    # Orders apps and the models within them. Keyed by app label.
    "order": {
        "blog": ["Post", "Author"],   # listed apps come first, in this order;
        "auth": [],                   # unlisted apps follow, alphabetically.
        "content": ["Post", "Article"],  # also positions the "content" group below —
                                          # a group's label works exactly like a real app's.
        # An empty list ([]) means "show all of this app's models, alphabetically".
        # A model not listed for an app still shows up, after the listed ones, alphabetically.
    },
    # Merges models from several apps into one synthetic sidebar heading.
    "custom_groups": {
        "content": {                          # synthetic app label — used as the key in "order" too
            "display_label": "Content",       # sidebar title (optional; defaults to "Content", from the key)
            "apps": {                          # source app label -> models to pull in
                "blog": ["Post"],
                "news": ["Article"],           # [] here would mean "take all of news's models"
            },
        },
        # A group left out of "order" defaults to alphabetical position, same as any app.
    },
}
```

Both top-level keys (`"order"`, `"custom_groups"`) are optional and independently
emptyable — set only the one you need, or neither (the package is a no-op with no
`ADMIN_APP_LIST` at all). The sections below cover each in detail.

## Install

```bash
pip install django-admin-applist-order
```

## Setup

Add the middleware (this is the only required step):

```python
MIDDLEWARE = [
    # ...
    "django_admin_applist_order.middleware.AppListOrderMiddleware",
]
```

## Usage

Define `ADMIN_APP_LIST` in `settings.py` (see the Quickstart above for a full example).
It has two independently optional keys:

- `"order"` — orders apps and the models within them. Keys are app labels (the
  app's folder name, e.g. `core`, `auth`).
- `"custom_groups"` — merges models from several apps into a synthetic sidebar
  heading.

If the setting is missing entirely, or `{}`, the package does nothing. Either
inner key can be omitted or left empty independently — the other still runs.

### Ordering (`ADMIN_APP_LIST["order"]`)

Behaviour:

- **Apps** listed in the dict appear first, in dict order. Apps not listed
  follow, sorted alphabetically by their display name.
- **Models** listed for an app appear first, in that order, followed by any
  unlisted models sorted alphabetically.
- An **empty list** means "show all of this app's models, sorted alphabetically".

For example, ordering the blog app's models first, and then the auth app's models:

```python
ADMIN_APP_LIST = {
    "order": {
        "blog": ["Author", "Post"],  # these first, alphabetical order will show the rest of the blog app models
        "auth": [],  # listed app, but all models will appear alphabetically
    },
}
```

### Grouping (`ADMIN_APP_LIST["custom_groups"]`)

Behaviour:

- Grouped models are **moved out** of their source apps. A source app left with no models
  disappears; one with leftover models stays.
- A group's `app_label` is its key (`"content"`), so `ADMIN_APP_LIST["order"]` treats it
  exactly like a real app: mention it there to position it and/or order its models; leave
  it out and it falls back to the same default an unmentioned real app gets — alphabetical,
  at the end.

  ```python
  ADMIN_APP_LIST = {
      "order": {
          "content": ["Post", "Article"],  # order within the group
          # ... other apps
      },
      "custom_groups": {
          "content": {"apps": {"blog": ["Post"], "news": ["Article"]}},
      },
  }
  ```

- Unknown source apps or models (e.g. not visible to the current user) are skipped silently.

## Deprecated settings

`ADMIN_APP_GROUPS` and `ADMIN_APPS_DISPLAY_ORDER` still work, but are deprecated in
favor of the consolidated `ADMIN_APP_LIST` above and emit a `DeprecationWarning`.
They'll be removed in a future major release.

```python
# Deprecated — still works, but warns:
ADMIN_APPS_DISPLAY_ORDER = {"auth": ["User", "Group"]}
ADMIN_APP_GROUPS = {"content": {"apps": {"blog": ["Post"]}}}

# Preferred:
ADMIN_APP_LIST = {
    "order": {"auth": ["User", "Group"]},
    "custom_groups": {"content": {"apps": {"blog": ["Post"]}}},
}
```

`ADMIN_APP_LIST` cannot be combined with the deprecated settings — pick one or the other.

## How it works

Django builds the app list in the response context under `app_list` (the
index page) and `available_apps` (the nav sidebar). The middleware groups and/or
reorders those lists in `process_template_response` according to `ADMIN_APP_LIST`
— grouping runs first, so a group's synthetic label can then be positioned via
the `"order"` config. Because it only touches the rendered context, it
composes cleanly with a default `admin.site` or any custom `AdminSite`.
