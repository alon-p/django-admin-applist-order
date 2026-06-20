# django-admin-applist-order

Order the Django admin **app list** — the apps shown on the admin index, and
the models within each app — from a single dict in your `settings.py`.

It works through a middleware that post-processes the admin's response, so you
**don't** need to swap your `AdminSite` or change any admin registration. Add
one line to `MIDDLEWARE`, define the setting, done.

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

## How it works

Django builds the app list in the response context under `app_list` (the
index page) and `available_apps` (the nav sidebar). The middleware reorders
those lists in `process_template_response` according to your setting. Because
it only touches the rendered context, it composes cleanly with a default
`admin.site` or any custom `AdminSite`.