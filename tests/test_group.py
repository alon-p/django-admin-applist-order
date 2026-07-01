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
        "display_label": "Content",
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
