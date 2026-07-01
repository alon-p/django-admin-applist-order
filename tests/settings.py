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

# Deliberately NOT Django's default order, so a passing test can only mean
# the middleware reordered things. Django's default for auth is Group, User
# (alphabetical by verbose_name_plural); we set User before Group to reverse it.
ADMIN_APP_LIST = {
    "order": {
        "sessions": [],        # listed first; models alpha-sorted
        "auth": ["User", "Group"],  # reverse of Django's default (Group, User)
    },
}