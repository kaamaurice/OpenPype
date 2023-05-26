import json
from typing import Generator

import bpy

import pyblish.api
from openpype.hosts.blender.api.pipeline import AVALON_PROPERTY


class CollectInstances(pyblish.api.ContextPlugin):
    """Collect the data of a model."""

    hosts = ["blender"]
    label = "Collect Instances"
    order = pyblish.api.CollectorOrder

    @staticmethod
    def get_collections() -> Generator:
        """Return all collections marked as OpenPype instance."""
        for collection in bpy.context.scene.collection.children_recursive:
            avalon_prop = collection.get(AVALON_PROPERTY) or dict()
            if avalon_prop.get("id") == "pyblish.avalon.instance":
                yield collection

    def process(self, context):
        """Collect the models from the current Blender scene."""
        collections = self.get_collections()

        for collection in collections:
            avalon_prop = collection[AVALON_PROPERTY]
            asset = avalon_prop["asset"]
            family = avalon_prop["family"]
            subset = avalon_prop["subset"]
            task = avalon_prop["task"]
            name = f"{asset}_{subset}"
            instance = context.create_instance(
                name=name,
                family=family,
                families=[family],
                subset=subset,
                asset=asset,
                task=task,
            )
            # Collect all objects recursively.
            objects = list(collection.all_objects)
            for obj in objects:
                objects.extend(list(obj.children))
            # Append all child objects and collections to instance members.
            members = list(set(objects) | set(collection.children_recursive))
            # Finally append the root collection.
            members.append(collection)
            instance[:] = members
            self.log.debug(json.dumps(instance.data, indent=4))
            for obj in instance:
                self.log.debug(obj)
