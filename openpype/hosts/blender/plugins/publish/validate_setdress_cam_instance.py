from typing import List

import bpy
import string

import pyblish.api

import openpype.hosts.blender.api.action
from openpype.pipeline.publish import ValidateContentsOrder


class ValidateSetdressCamInstance(pyblish.api.Validator):
    """Validate that cam and review instances points on the right collection."""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["setdress"]
    label = "Validate SetDress Cam Review Instances"
    actions = [openpype.hosts.blender.api.action.SelectInvalidAction]
    optional = False

    @staticmethod
    def get_invalid(instance) -> List:
        invalid = []

        # Get all openpype instances
        all_instances = bpy.context.scene.openpype_instances

        for inst in all_instances:
            # Check only cameraMain and reviewMain instances
            if inst.name.find("cameraMain") != -1 or inst.name.find("reviewMain") != -1:
                datablocks = None
                datablocks = inst.get_datablocks()
                # Check if the datablocks set is not empty
                if len(list(datablocks)) > 0:
                    for datablock in datablocks:
                        # Check if the datablock is not a collection
                        if type(datablock) is not bpy.types.Collection and inst.name not in invalid:
                            invalid.append(inst.name)
                else:
                    invalid.append(inst.name)
        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError(
                f"Instance(s) {invalid} is/are not pointing on a collection."
            )
