"""Create a camera asset."""

import bpy

from openpype.pipeline import legacy_io
from openpype.hosts.blender.api import plugin, lib
from openpype.hosts.blender.api.utils import context_window
from openpype.hosts.blender.api.pipeline import AVALON_INSTANCES


class CreateCamera(plugin.Creator):
    """Polygonal static geometry"""

    name = "cameraMain"
    label = "Camera"
    family = "camera"
    icon = "video-camera"

    @context_window
    def process(self):
        # Get Instance Container or create it if it does not exist
        instances = bpy.data.collections.get(AVALON_INSTANCES)
        if not instances:
            instances = bpy.data.collections.new(name=AVALON_INSTANCES)
            bpy.context.scene.collection.children.link(instances)

        # Create instance object
        asset = self.data["asset"]
        subset = self.data["subset"]
        name = plugin.asset_name(asset, subset)

        asset_group = bpy.data.objects.new(name=name, object_data=None)
        asset_group.empty_display_type = 'SINGLE_ARROW'
        instances.objects.link(asset_group)
        self.data['task'] = legacy_io.Session.get('AVALON_TASK')
        print(f"self.data: {self.data}")
        lib.imprint(asset_group, self.data)

        if (self.options or {}).get("useSelection"):
            bpy.context.view_layer.objects.active = asset_group
            selected = lib.get_selection()
            for obj in selected:
                obj.select_set(True)
            selected.append(asset_group)
            bpy.ops.object.parent_set(keep_transform=True)
        else:
            plugin.deselect_all()
            camera = bpy.data.cameras.new(subset)
            camera_obj = bpy.data.objects.new(subset, camera)

            instances.objects.link(camera_obj)

            camera_obj.select_set(True)
            asset_group.select_set(True)
            bpy.context.view_layer.objects.active = asset_group
            bpy.ops.object.parent_set(keep_transform=True)

        return asset_group
