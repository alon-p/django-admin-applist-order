"""Merge models from several apps into synthetic sidebar groups.

Framework-free, mirroring ``reorder.py``: operates on the plain list-of-dicts
structure Django builds for the admin index and nav sidebar. Each app dict has
``app_label``, ``name``, ``app_url`` and ``models``; each model dict has
``object_name``, ``name`` and ``admin_url``.
"""

import logging

from .exceptions import MalformedAppGroupsException

logger = logging.getLogger(__name__)


def group_app_list(app_list, app_groups, setting_name="ADMIN_APP_GROUPS"):
    """Return a new app list with models merged into synthetic group entries.

    ``app_groups`` is the ADMIN_APP_GROUPS mapping::

        {group_label: {"display_label": "Title", "apps": {app_label: [ModelName, ...]}}}

    ``setting_name`` is only used to name the offending setting in raised
    exceptions — pass it when ``app_groups`` came from somewhere other than a
    literal ``ADMIN_APP_GROUPS`` (e.g. ``ADMIN_APP_LIST["custom_groups"]``).

    Rules:
      * Each ``group_label`` becomes a synthetic app whose ``app_label`` is that
        label, so it can be positioned / model-ordered via ``ADMIN_APP_LIST["order"]``
        exactly like a real app — including its *default* position when unmentioned:
        alphabetical, at the end, same as any other unlisted app. This function
        doesn't pick a position; it only builds the group and appends it after the
        remaining real apps. Final placement is ``reorder_app_list``'s job.
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


def _take_models(app, model_names, group_label):
    """Remove and return the requested models from ``app`` in place.

    Empty ``model_names`` takes all models. Unknown names are skipped + logged.
    Returned models preserve the order given in ``model_names``.
    """
    if not model_names:
        taken = app["models"]
        app["models"] = []
        return taken

    by_name = {m["object_name"].lower(): m for m in app["models"]}
    taken = []
    for name in model_names:
        model = by_name.get(name.lower())
        if model is None:
            logger.debug(
                "group %r: model %r not found in app %r — skipping",
                group_label, name, app["app_label"],
            )
            continue
        taken.append(model)

    taken_ids = {id(m) for m in taken}
    app["models"] = [m for m in app["models"] if id(m) not in taken_ids]
    return taken


def _make_group(group_label, display_label, models):
    """Build a synthetic app dict shaped like the ones Django produces."""
    return {
        "name": display_label or group_label.replace("_", " ").title(),
        "app_label": group_label,
        # No dedicated index page for a synthetic group; land on the first model.
        # (Simpler than overriding admin templates to render a link-less title.)
        "app_url": models[0].get("admin_url", "") if models else "",
        "has_module_perms": True,
        "models": models,
    }
