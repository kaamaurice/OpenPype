import pyblish.api

from openpype.hosts.blender.api.utils import (
    AVALON_PROPERTY,
)
from openpype.hosts.blender.api.lib import get_root_containers_from_datablocks


class CollectUpstreamInputs(pyblish.api.InstancePlugin):
    """Collect input source inputs for this publish.

    This will include `inputs` data of which loaded publishes were used in the
    generation of this publish. This leaves an upstream trace to what was used
    as input. Representation ObjectId is used to identify the input.
    """

    label = "Collect Inputs"
    order = pyblish.api.CollectorOrder + 0.34
    hosts = ["blender"]

    def process(self, instance):
        # Collect all input representations used by the instance
        instance.data["inputRepresentations"] = [
            c[AVALON_PROPERTY]["representation"]
            for c in get_root_containers_from_datablocks(instance)
        ]
