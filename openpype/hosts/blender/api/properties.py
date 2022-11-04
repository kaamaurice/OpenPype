"""Blender properties."""

import bpy
from bpy.types import PropertyGroup
from bpy.utils import register_classes_factory


class OpenpypeInstance(PropertyGroup):
    name: bpy.props.StringProperty(name="OpenPype Instance name")

    # = Custom properties =
    # datablocks (List): all datablocks related to this instance


classes = [
    OpenpypeInstance,
]


factory_register, factory_unregister = register_classes_factory(classes)


def register():
    "Register the properties."
    factory_register()

    bpy.types.Scene.openpype_instances = bpy.props.CollectionProperty(
        type=OpenpypeInstance, name="OpenPype Instances"
    )
    bpy.types.Scene.openpype_instance_active_index = bpy.props.IntProperty(
        name="OpenPype Instance Active Index"
    )
    bpy.types.Collection.is_openpype_instance = bpy.props.BoolProperty()


def unregister():
    """Unregister the properties."""
    factory_unregister()

    del bpy.types.Scene.openpype_instances
