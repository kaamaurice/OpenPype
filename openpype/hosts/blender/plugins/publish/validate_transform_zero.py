from typing import List

import mathutils
import bpy
import pyblish.api
import openpype.hosts.blender.api.action
from openpype.hosts.blender.api import plugin


class ValidateTransformZero(pyblish.api.InstancePlugin):
    """Transforms can't have any values

    To solve this issue, try freezing the transforms. So long
    as the transforms, rotation and scale values are zero,
    you're all good.

    """

    order = openpype.api.ValidateContentsOrder
    hosts = ["blender"]
    families = ["model"]
    category = "geometry"
    version = (0, 1, 0)
    label = "Transform Zero"
    actions = [openpype.hosts.blender.api.action.SelectInvalidAction]

    _identity = mathutils.Matrix()

    @classmethod
    def get_invalid(cls, instance) -> List:
        invalid = []
        container = bpy.data.collections.get(instance.name)
        objects = plugin.get_all_objects_in_collection(container)
        for obj in objects:
            if obj.matrix_basis != cls._identity:
                invalid.append(obj)
        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError(
                f"Object found in instance is not transform zero: {invalid}"
            )
