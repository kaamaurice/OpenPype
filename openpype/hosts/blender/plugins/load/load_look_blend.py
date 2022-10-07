"""Load and assign extracted materials from look task."""

from typing import Dict, Tuple, Union

import bpy

from openpype.hosts.blender.api import plugin


class MaterialLookLoader(plugin.AssetLoader):
    """Load and assign extracted materials from look task."""

    families = ["look"]
    representations = ["blend"]

    label = "Load Materials"
    icon = "paint-brush"
    color = "orange"
    color_tag = "COLOR_07"
    order = 3
    no_namespace = True

    def _process(self, libpath, asset_group):

        container = self._load_library_collection(libpath)

        materials_assignment = container["materials_assignment"].to_dict()
        materials_indexes = container["materials_indexes"].to_dict()

        asset_group["materials_assignment"] = materials_assignment

        for obj in bpy.context.scene.objects:
            obj_name = obj.name
            original_name = obj_name.split(":")[-1]

            materials = materials_assignment.get(original_name)
            if materials and obj.type == "MESH":

                if obj.override_library or obj.library:
                    obj = plugin.make_local(obj)

                for idx, material in enumerate(materials):
                    if len(obj.material_slots) <= idx:
                        obj.data.materials.append(material)
                    obj.material_slots[idx].link = "OBJECT"
                    obj.material_slots[idx].material = material

                plugin.link_to_collection(obj, asset_group)

            mtl_idx = materials_indexes.get(original_name)
            if mtl_idx and obj.type == "MESH":
                for idx, face in enumerate(obj.data.polygons):
                    face.material_index = (
                        mtl_idx[idx] if len(mtl_idx) > idx else 0
                    )

    @staticmethod
    def _remove_container(container: Dict) -> bool:
        """Remove an existing container from a Blender scene.
        Arguments:
            container: Container to remove.
        Returns:
            bool: Whether the container was deleted.
        """
        object_name = container["objectName"]
        asset_group = bpy.data.collections.get(object_name)

        if not asset_group:
            return False

        # Unassign materials.
        if asset_group.get("materials_assignment"):

            mtl_assignment = asset_group["materials_assignment"].to_dict()

            for obj in bpy.context.scene.objects:
                obj_name = obj.name
                original_name = obj_name.split(":")[-1]

                materials = mtl_assignment.get(original_name)
                if materials and obj.type == "MESH":
                    for idx, material in enumerate(materials):
                        if len(obj.material_slots) > idx:
                            obj.material_slots[idx].material = None
                        material.use_fake_user = False
                    while len(obj.data.materials):
                        obj.data.materials.pop()

        # Unlink all child objects and collections.
        for obj in asset_group.objects:
            asset_group.objects.unlink(obj)
        for child in asset_group.children:
            asset_group.children.unlink(child)

        plugin.remove_container(asset_group)
        plugin.orphans_purge()

        return True

    def exec_update(
        self, container: Dict, representation: Dict
    ) -> Tuple[str, Union[bpy.types.Collection, bpy.types.Object]]:
        # Get objects using look materials
        mat_slots = set()
        asset_group = self._get_asset_group_container(container)
        for obj in bpy.data.objects:
            mat_slots.update(
                {
                    slot
                    for slot in obj.material_slots
                    if slot.material.library
                    and slot.material.library.filepath == container["libpath"]
                }
            )

        # Remove material from slots and
        # determine if single material
        material_names = []
        single_material = True
        for slot in mat_slots:
            if list(mat_slots)[0].material != slot.material:
                single_material = False

            material_names.append((slot, slot.material.name))
            slot.material = None

        # Execute update
        asset_group = super().exec_update(container, representation)

        # Reassign slots with changed new material only if one material on both sides
        new_materials = [
            mat
            for mat in bpy.data.materials
            if mat.library
            and mat.library.filepath == asset_group["avalon"]["libpath"]
        ]
        if single_material and len(new_materials) == 1:
            for slot in mat_slots:
                slot.material = new_materials[0]
            return

        # Reassign slots by name
        for slot, material_name in material_names:
            new_material = bpy.data.materials.get(material_name)
            if new_material:
                slot.material = new_material
            else:
                print(
                    f"WARNING|Slot {slot}: no matched material with name '{material_name}'. Slot left empty."
                )
