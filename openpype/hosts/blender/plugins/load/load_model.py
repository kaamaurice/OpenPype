"""Load a model asset in Blender."""

from typing import Dict, Tuple, Union

import bpy

from openpype.hosts.blender.api import plugin


class LinkModelLoader(plugin.AssetLoader):
    """Link models from a .blend file."""

    families = ["model"]
    representations = ["blend"]

    label = "Link Model"
    icon = "link"
    color = "orange"
    color_tag = "COLOR_04"
    order = 0

    load_type = "LINK"

    bl_types = frozenset({bpy.types.Collection, bpy.types.Object})


class AppendModelLoader(plugin.AssetLoader):
    """Append models from a .blend file."""

    families = ["model"]
    representations = ["blend"]

    label = "Append Model"
    icon = "paperclip"
    color = "orange"
    color_tag = "COLOR_04"
    order = 1

    load_type = "APPEND"

    bl_types = frozenset({bpy.types.Collection, bpy.types.Object})


class InstanceModelLoader(plugin.AssetLoader):
    """load models from a .blend file as instance collection."""

    families = ["model"]
    representations = ["blend"]

    label = "Instantiate Collection"
    icon = "archive"
    color = "orange"
    color_tag = "COLOR_04"
    order = 2

    load_type = "INSTANCE"
    
    bl_types = frozenset({bpy.types.Collection, bpy.types.Object})

    def _apply_options(self, asset_group, options):
        """Apply load options fro asset_group."""

        transform = options.get("transform")
        parent = options.get("parent")

        if transform:
            location = transform.get("translation")
            rotation = transform.get("rotation")
            scale = transform.get("scale")

            asset_group.location = [location[n] for n in "xyz"]
            asset_group.rotation_euler = [rotation[n] for n in "xyz"]
            asset_group.scale = [scale[n] for n in "xyz"]

        if isinstance(parent, bpy.types.Object):
            with plugin.context_override(active=parent, selected=asset_group):
                bpy.ops.object.parent_set(keep_transform=True)
        elif isinstance(parent, bpy.types.Collection):
            for current_parent in asset_group.users_collection:
                current_parent.children.unlink(asset_group)
            plugin.link_to_collection(asset_group, parent)
        

    # def _load_process(self, libpath, container_name):
    #     all_datablocks, container_collection = super()._load_process(libpath, container_name)

    #     # Create empty object
    #     instance_object = bpy.data.objects.new(container_collection.name, object_data=None)
    #     plugin.get_main_collection().objects.link(instance_object)

    #     # Instance collection to object
    #     instance_object.instance_collection = container_collection
    #     instance_object.instance_type = "COLLECTION"
        
    #     return all_datablocks, container_collection

    # def process_asset(
    #     self,
    #     context: dict,
    #     name: str,
    #     namespace: Optional[str] = None,
    #     options: Optional[Dict] = None,
    # ) -> Union[bpy.types.Object, bpy.types.Collection]:
    #     """
    #     Arguments:
    #         name: Use pre-defined name
    #         namespace: Use pre-defined namespace
    #         context: Full parenthood of representation to load
    #         options: Additional settings dictionary
    #     """
    #     datablocks, container_collection = 

       

    #     return datablocks, container_collection

    def exec_switch(
        self, container: Dict, representation: Dict
    ) -> Tuple[Union[bpy.types.Collection, bpy.types.Object]]:
        """Switch the asset using update"""
        if container["loader"] != "InstanceModelLoader":
            raise NotImplementedError("Not implemented yet")

        asset_group = self.exec_update(container, representation)

        # Update namespace if needed

        return asset_group
