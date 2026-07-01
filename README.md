# django-admin-applist-order

> A simple Django middleware to reorder and group the admin app list from settings in `settings.py`.

Order the Django admin **app list** — the apps shown on the admin index, and
the models within each app — from a single dict in your `settings.py`. You can
also merge models from several apps under one synthetic sidebar heading with
`ADMIN_APP_GROUPS`.

It works through a middleware that post-processes the admin's response, so you
**don't** need to swap your `AdminSite` or change any admin registration. Add
one line to `MIDDLEWARE`, define the setting(s), done.

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

Define `ADMIN_APPS_DISPLAY_ORDER` in `settings.py`. Keys are app labels (the
app's folder name, e.g. `core`, `auth`).

```python 
ADMIN_APPS_DISPLAY_ORDER = {
    "APP_NAME": ["MODEL1", "MODEL2", "MODEL3"],
}
```

Behaviour:

- **Apps** listed in the dict appear first, in dict order. Apps not listed
  follow, sorted alphabetically by their display name.
- **Models** listed for an app appear first, in that order, followed by any
  unlisted models sorted alphabetically.
- An **empty list** means "show all of this app's models, sorted alphabetically".
- If the setting is missing or empty, the package does nothing.

For example, ordering the blog app's models first, and then the auth app's models:

```python
ADMIN_APPS_DISPLAY_ORDER = {
    "blog": ["Author", "Post"],  # these first, alphabetical order will show the rest of the blog app models
    "auth": [],  # listed app, but all models will appear by  alphabetical
}
```

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

## How it works

Django builds the app list in the response context under `app_list` (the
index page) and `available_apps` (the nav sidebar). The middleware groups and/or
reorders those lists in `process_template_response` according to your settings
— grouping runs first, so a group's synthetic label can then be positioned via
`ADMIN_APPS_DISPLAY_ORDER`. Because it only touches the rendered context, it
composes cleanly with a default `admin.site` or any custom `AdminSite`.