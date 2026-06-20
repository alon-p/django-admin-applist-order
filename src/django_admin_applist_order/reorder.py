"""Pure reordering logic, deliberately framework-free so it's easy to test.

The functions here operate on the plain list-of-dicts structure Django builds
for the admin index and nav sidebar. Each app dict has ``app_label``, ``name``
and ``models``; each model dict has ``object_name`` and ``name``.
"""

import logging

logger = logging.getLogger(__name__)


def reorder_app_list(app_list, apps_order):
    """Return a new app list ordered according to ``apps_order``.

    ``apps_order`` is the ADMIN_APPS_DISPLAY_ORDER mapping::

        {app_label: [ModelName, ...]}

    Rules:
      * Apps listed in the mapping come first, in mapping order.
      * Apps not listed follow, sorted alphabetically by their display name.
      * Within an app, models listed in the value come first (in that order),
        followed by any unlisted models sorted alphabetically.
      * An empty list for an app means "all models, sorted alphabetically".
    """
    app_dict = {app["app_label"]: app for app in app_list}

    listed_labels = [label for label in apps_order if label in app_dict]
    unlisted_labels = sorted(
        (label for label in app_dict if label not in apps_order),
        key=lambda label: app_dict[label]["name"].lower(),
    )

    ordered = [app_dict[label] for label in listed_labels]
    ordered += [app_dict[label] for label in unlisted_labels]

    for app in ordered:
        _order_models(app, apps_order.get(app["app_label"], []))

    return ordered


def _order_models(app, model_order):
    """Reorder ``app['models']`` in place according to ``model_order``."""
    wanted = [name.lower() for name in model_order]

    model_by_name = {model["object_name"].lower(): model for model in app["models"]}
    listed = []
    for name in wanted:
        model = model_by_name.get(name)
        if model is None:
            logger.warning("model %r not found in app %r, skipping", name, app["app_label"])
        else:
            listed.append(model)
    unlisted = sorted(
        (
            model
            for model in app["models"]
            if model["object_name"].lower() not in wanted
        ),
        key=lambda model: model["name"],
    )
    app["models"] = listed + unlisted
