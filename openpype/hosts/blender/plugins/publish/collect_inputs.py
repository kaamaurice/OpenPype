import itertools

import pyblish.api
from openpype.hosts.blender.api.utils import (
    AVALON_PROPERTY,
    BL_OUTLINER_TYPES,
    get_all_outliner_children,
)


class CollectUpstreamInputs(pyblish.api.InstancePlugin):
    """Collect input source inputs for this publish.

    This will include `inputs` data of which loaded publishes were used in the
    generation of this publish. This leaves an upstream trace to what was used
    as input.
    """

    label = "Collect Inputs"
    order = pyblish.api.CollectorOrder + 0.34
    hosts = ["blender"]

    def process(self, instance):
        # Find all datablocks used by the instance
        datablocks = set(
            itertools.chain.from_iterable(
                get_all_outliner_children(d)
                for d in instance
                if isinstance(d, tuple(BL_OUTLINER_TYPES))
            )
        ) | set(instance)

        # Collect all input representations used by the instance
        instance.data["inputRepresentations"] = [
            d[AVALON_PROPERTY]["representation"]
            for d in datablocks
            if d.get(AVALON_PROPERTY, {}).get("representation")
        ]
