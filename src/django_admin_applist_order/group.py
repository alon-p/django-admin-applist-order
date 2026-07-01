"""Merge models from several apps into synthetic sidebar groups.

Framework-free, mirroring ``reorder.py``: operates on the plain list-of-dicts
structure Django builds for the admin index and nav sidebar. Each app dict has
``app_label``, ``name``, ``app_url`` and ``models``; each model dict has
``object_name``, ``name`` and ``admin_url``.
"""

import logging

from .exceptions import MalformedAppGroupsException

logger = logging.getLogger(__name__)


def group_app_list(app_list, app_groups):
    """Return a new app list with models merged into synthetic group entries.

    ``app_groups`` is the ADMIN_APP_GROUPS mapping::

        {group_label: {"name": "Title", "apps": {app_label: [ModelName, ...]}}}

    Rules:
      * Each ``group_label`` becomes a synthetic app whose ``app_label`` is that
        label, so it can be positioned / model-ordered via
        ADMIN_APPS_DISPLAY_ORDER exactly like a real app.
      * Listed models are moved out of their source app into the group. An empty
        list pulls all of the source app's models.
      * A source app left with no models is dropped; one with leftovers stays.
      * The group takes the slot of its first present source app. A group that
        collects no models (all sources absent) is not emitted.
      * Unknown source apps / models are skipped and logged at DEBUG, mirroring
        ``reorder_app_list``. Wrong value *types* raise MalformedAppGroupsException.
    """
    if not isinstance(app_groups, dict):
        raise MalformedAppGroupsException.for_setting(app_groups)

    app_by_label = {app["app_label"]: app for app in app_list}
    collected_by_group = {}   # group_label -> [model dicts]
    anchor_by_group = {}      # group_label -> app_label its slot should replace

    for group_label, definition in app_groups.items():
        if not isinstance(definition, dict) or not isinstance(definition.get("apps"), dict):
            raise MalformedAppGroupsException.for_group(group_label, definition)

        collected = []
        anchor = None
        for source_label, model_names in definition["apps"].items():
            if not isinstance(model_names, list):
                raise MalformedAppGroupsException.for_app(group_label, source_label, model_names)
            source = app_by_label.get(source_label)
            if source is None:
                logger.debug(
                    "group %r: source app %r not found — skipping", group_label, source_label
                )
                continue
            if anchor is None:
                anchor = source_label
            collected.extend(_take_models(source, model_names, group_label))

        collected_by_group[group_label] = collected
        anchor_by_group[group_label] = anchor

    # Rebuild: insert each non-empty group at its anchor app's slot; drop apps
    # that were fully consumed.
    result = []
    inserted = set()
    for app in app_list:
        for group_label, anchor in anchor_by_group.items():
            if (
                anchor == app["app_label"]
                and group_label not in inserted
                and collected_by_group[group_label]
            ):
                result.append(
                    _make_group(
                        group_label,
                        app_groups[group_label].get("name"),
                        collected_by_group[group_label],
                    )
                )
                inserted.add(group_label)
        if app["models"]:
            result.append(app)

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


def _make_group(group_label, name, models):
    """Build a synthetic app dict shaped like the ones Django produces."""
    return {
        "name": name or group_label.replace("_", " ").title(),
        "app_label": group_label,
        # No dedicated index page for a synthetic group; land on the first model.
        # (Simpler than overriding admin templates to render a link-less title.)
        "app_url": models[0].get("admin_url", "") if models else "",
        "has_module_perms": True,
        "models": models,
    }
