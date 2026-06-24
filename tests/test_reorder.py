import pytest

from django_admin_applist_order.reorder import reorder_app_list


def make_app(app_label, name, *model_names):
    return {
        "app_label": app_label,
        "name": name,
        "models": [{"object_name": m, "name": m} for m in model_names],
    }


def model_object_names(app):
    return [m["object_name"] for m in app["models"]]


def app_labels(app_list):
    return [a["app_label"] for a in app_list]


def assert_app_order(apps, order, expected):
    app_list = [make_app(label, label.title()) for label in apps]
    result = reorder_app_list(app_list, order)
    assert app_labels(result) == expected


def assert_model_order(models, order, expected):
    app = make_app("blog", "Blog", *models)
    result = reorder_app_list([app], {"blog": order})
    assert model_object_names(result[0]) == expected


def test_empty_list_returns_empty():
    assert_app_order(
        apps=[],
        order={"auth": []},
        expected=[],
    )


def test_no_order_sorts_apps_alphabetically():
    assert_app_order(
        apps=["zebra", "alpha", "middle"],
        order={},
        expected=["alpha", "middle", "zebra"],
    )


def test_listed_apps_follow_mapping_order():
    assert_app_order(
        apps=["auth", "blog", "shop"],
        order={"shop": [], "auth": [], "blog": []},
        expected=["shop", "auth", "blog"],
    )


def test_unlisted_apps_come_after_listed_sorted_alphabetically():
    assert_app_order(
        apps=["zebra", "auth", "blog"],
        order={"zebra": []},
        expected=["zebra", "auth", "blog"],
    )


def test_order_label_missing_from_list_is_ignored():
    assert_app_order(
        apps=["auth"],
        order={"missing": [], "auth": []},
        expected=["auth"],
    )


def test_empty_model_order_sorts_models_alphabetically():
    assert_model_order(
        models=["Post", "Author", "Comment"],
        order=[],
        expected=["Author", "Comment", "Post"],
    )


def test_unlisted_models_come_after_listed_sorted_alphabetically():
    assert_model_order(
        models=["Post", "Author", "Comment", "Tag"],
        order=["Tag", "Post"],
        expected=["Tag", "Post", "Author", "Comment"],
    )


def test_model_name_matching_is_case_insensitive():
    assert_model_order(
        models=["Post", "Author"],
        order=["post", "author"],
        expected=["Post", "Author"],
    )


def test_unknown_model_in_order_is_skipped_not_an_error():
    app = make_app("blog", "Blog", "Post", "Author")
    result = reorder_app_list([app], {"blog": ["Ghost", "Post"]})
    assert model_object_names(result[0]) == ["Post", "Author"]


def test_unknown_model_in_order_logs_at_debug(caplog):
    import logging

    app = make_app("blog", "Blog", "Post", "Author")
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.reorder"):
        reorder_app_list([app], {"blog": ["Ghost", "Post"]})
    assert any("ghost" in record.message.lower() for record in caplog.records)
    assert any("blog" in record.message.lower() for record in caplog.records)


def test_unknown_app_in_order_logs_at_debug(caplog):
    import logging

    app_list = [make_app("auth", "Auth", "User")]
    with caplog.at_level(logging.DEBUG, logger="django_admin_applist_order.reorder"):
        reorder_app_list(app_list, {"ghost_app": [], "auth": []})
    assert any("ghost_app" in record.message.lower() for record in caplog.records)
