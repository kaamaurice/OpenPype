from typing import List

import bpy
import string

import pyblish.api

import openpype.hosts.blender.api.action
from openpype.pipeline.publish import ValidateContentsOrder


class ValidateReviewCamInstance(pyblish.api.Validator):
    """Validate that cam and review instances point to the right collection."""

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["review", "camera"]
    label = "Validate Cam Review Instances"
    actions = [openpype.hosts.blender.api.action.SelectInvalidAction]
    optional = False

    @staticmethod
    def get_invalid(instance) -> List:
        invalid = []

        for obj in instance:
            # Check if the object is not a collection
            if not isinstance(obj, bpy.types.Collection) and instance not in invalid:
                invalid.append(instance)
        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError(
                f"Instance(s) {invalid} is/are not pointing to a collection."
            )
