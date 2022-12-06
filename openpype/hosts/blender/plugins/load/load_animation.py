"""Load an animation in Blender."""

from typing import Dict, Optional

import bpy

from openpype.hosts.blender.api import plugin


class AnimationLoader(plugin.AssetLoader):
    """Load animations from a .blend file."""

    color = "orange"
    color_tag = "COLOR_07"

    bl_types = frozenset({bpy.types.Action})

    def _remove_actions_from_library(self, asset_group):
        """Remove action from all objects in asset_group"""
        for obj in asset_group.all_objects:
            if obj.animation_data and obj.animation_data.action:
                obj.animation_data.action = None

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container: Container to remove.

        Returns:
            bool: Whether the container was deleted.
        """
        scene_container = self._get_asset_group_container(container)

        # if scene_container:

        #     # Remove actions from asset_group container.
        #     self._remove_actions_from_library(scene_container)

        #     # Unlink all child objects and collections.
        #     for obj in scene_container.objects:
        #         scene_container.objects.unlink(obj)
        #     for child in scene_container.children:
        #         scene_container.children.unlink(child)

        return super().exec_remove(container)

    def load(
        self,
        context: dict,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[bpy.types.Collection]:
        datablocks, container = super().load(context, name, namespace, options)

        # Try to assign linked actions by parsing their name.
        for action in [d for d in datablocks if type(d) is bpy.types.Action]:

            # collection_name = action.get("collection", "")
            armature_name = action.get("armature", "")

            # collection = next(
            #     (c for c in scene_collections if c.name == collection_name),
            #     None
            # )
            
            armature = bpy.context.scene.objects.get(armature_name)
            # if not collection_name:
            #     armature = bpy.context.scene.objects.get(armature_name)
            # else:
            #     assert collection, (
            #         f"invalid collection name '{collection_name}' "
            #         f"for action: {action.name}"
            #     )
            #     armature = collection.all_objects.get(armature_name)

            if not armature:
                self.log.debug(
                    f"invalid armature name '{armature_name}' "
                    f"for action: {action.name}"
                )
                continue

            if not armature.animation_data:
                armature.animation_data_create()
            armature.animation_data.action = action

            # container_collection = container.get("outliner_entity")
            # if not container_collection:
            #     continue

            # if collection:
            #     plugin.link_to_collection(collection, container_collection)
            # else:
            #     plugin.link_to_collection(armature, container_collection)

        return datablocks, container  # TODO Test actions reassignation


class LinkAnimationLoader(AnimationLoader):
    """Link animations from a .blend file."""

    families = ["animation"]
    representations = ["blend"]

    label = "Link Animation"
    icon = "link"
    order = 0

    load_type = "LINK"

    def _remove_actions_from_library(self, asset_group):
        """Restore action from override library reference animation data."""
        for obj in asset_group.all_objects:
            if (
                obj.animation_data
                and obj.override_library
                and obj.override_library.reference
                and obj.override_library.reference.animation_data
                and obj.override_library.reference.animation_data.action
            ):
                obj.animation_data.action = (
                    obj.override_library.reference.animation_data.action
                )


class AppendAnimationLoader(AnimationLoader):
    """Append animations from a .blend file."""

    families = ["animation"]
    representations = ["blend"]

    label = "Append Animation"
    icon = "paperclip"
    order = 1

    load_type = "APPEND"
