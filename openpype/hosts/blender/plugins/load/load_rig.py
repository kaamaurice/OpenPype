"""Load a rig asset in Blender."""

from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional

import bpy

from openpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
)
from openpype.hosts.blender.api import plugin
from openpype.hosts.blender.api.pipeline import AVALON_PROPERTY


class BlendRigLoader(plugin.AssetLoader):
    """Load rigs from a .blend file."""

    families = ["rig"]
    representations = ["blend"]

    label = "Link Rig"
    icon = "code-fork"
    color = "orange"

    @staticmethod
    def _remove(asset_group):
        # remove all objects in asset_group
        objects = list(asset_group.objects)
        for obj in objects:
            try:
                objects.extend(obj.children)
                bpy.data.objects.remove(obj)
            except:
                pass
        # remove all collections in asset_group
        childrens = list(asset_group.children)
        for child in childrens:
            childrens.extend(child.children)
            bpy.data.collections.remove(child)

    @staticmethod
    def _process(libpath, group_name):
        with bpy.data.libraries.load(
            libpath, link=True, relative=False
        ) as (data_from, data_to):
            data_to.collections = data_from.collections

        container = None

        # get valid container from loaded collections
        for collection in data_to.collections:
            collection_metadata = collection.get(AVALON_PROPERTY)
            if (
                collection_metadata and
                collection_metadata.get("family") == "rig" and
                collection_metadata.get("asset") == group_name.split("_")[0]
            ):
                container = collection
                break

        assert container, "No asset container found"

        for obj in container.all_objects:
            obj.name = f"{group_name}:{obj.name}"

        # Create override library for container and elements.
        override = container.override_hierarchy_create(
            bpy.context.scene,
            bpy.context.view_layer,
        )
        # Get the first collection if only child or the scene root collection
        # to use it as asset group parent collection.
        parent_collection = bpy.context.scene.collection
        if len(parent_collection.children) == 1:
            parent_collection = parent_collection.children[0]

        # Relink and rename the override container using asset_group.
        bpy.context.scene.collection.children.unlink(override)
        parent_collection.children.link(override)
        override.name = group_name

        # clear and assign asset_group and objects variables
        bpy.data.collections.remove(container)
        asset_group = override
        objects = list(override.all_objects)

        bpy.data.orphans_purge(do_local_ids=False)

        plugin.deselect_all()

        return asset_group, objects

    def process_asset(
        self, context: dict, name: str, namespace: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[List]:
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        libpath = self.fname
        asset = context["asset"]["name"]
        subset = context["subset"]["name"]

        asset_name = plugin.asset_name(asset, subset)
        unique_number = plugin.get_unique_number(asset, subset)
        group_name = plugin.asset_name(asset, subset, unique_number)
        namespace = namespace or f"{asset}_{unique_number}"

        asset_group, objects = self._process(libpath, group_name)

        # update avalon metadata
        asset_group[AVALON_PROPERTY] = {
            "schema": "openpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(context["representation"]["_id"]),
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": str(context["representation"]["parent"]),
            "family": context["representation"]["context"]["family"],
            "objectName": group_name
        }

        self[:] = objects
        return objects

    def exec_update(self, container: Dict, representation: Dict):
        """Update the loaded asset.

        This will remove all objects of the current collection, load the new
        ones and add them to the collection.
        If the objects of the collection are used in another collection they
        will not be removed, only unlinked. Normally this should not be the
        case though.
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)
        libpath = Path(get_representation_path(representation))
        extension = libpath.suffix.lower()

        if not asset_group:
            asset_group = bpy.data.collections.get(object_name)

        self.log.info(
            "Container: %s\nRepresentation: %s",
            pformat(container, indent=2),
            pformat(representation, indent=2),
        )

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )
        assert libpath, (
            "No existing library file found for {container['objectName']}"
        )
        assert libpath.is_file(), (
            f"The file doesn't exist: {libpath}"
        )
        assert extension in plugin.VALID_EXTENSIONS, (
            f"Unsupported file: {libpath}"
        )

        metadata = asset_group.get(AVALON_PROPERTY)
        group_libpath = metadata["libpath"]

        normalized_group_libpath = (
            str(Path(bpy.path.abspath(group_libpath)).resolve())
        )
        normalized_libpath = (
            str(Path(bpy.path.abspath(str(libpath))).resolve())
        )
        self.log.debug(
            "normalized_group_libpath:\n  %s\nnormalized_libpath:\n  %s",
            normalized_group_libpath,
            normalized_libpath,
        )
        if normalized_group_libpath == normalized_libpath:
            self.log.info("Library already loaded, not updating...")
            return

        # Check how many assets use the same library
        count = 0
        assets = [o for o in bpy.data.objects if o.get(AVALON_PROPERTY)]
        assets += [c for c in bpy.data.collections if c.get(AVALON_PROPERTY)]
        for asset in assets:
            if asset.get(AVALON_PROPERTY).get('libpath') == libpath:
                count += 1

        # Get the armature of the rig
        objects = asset_group.all_objects
        armature = [obj for obj in objects if obj.type == 'ARMATURE'][0]

        action = None
        if armature.animation_data and armature.animation_data.action:
            action = armature.animation_data.action

        self._remove(asset_group)

        # If it is the last object to use that library, remove it
        if count == 1:
            library = bpy.data.libraries.get(bpy.path.basename(group_libpath))
            if library:
                bpy.data.libraries.remove(library)

        asset_group, objects = self._process(str(libpath), object_name)

        if action:
            for obj in objects:
                if obj.animation_data is None:
                    obj.animation_data_create()
                obj.animation_data.action = action

        metadata = asset_group.get(AVALON_PROPERTY)
        metadata["libpath"] = str(libpath)
        metadata["representation"] = str(representation["_id"])
        metadata["parent"] = str(representation["parent"])

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (openpype:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted.
        """
        object_name = container["objectName"]
        asset_group = bpy.data.objects.get(object_name)

        if not asset_group:
            asset_group = bpy.data.collections.get(object_name)

        if not asset_group:
            return False

        # Check how many assets use the same library
        libpath = asset_group.get(AVALON_PROPERTY).get('libpath')
        count = 0
        assets = [o for o in bpy.data.objects if o.get(AVALON_PROPERTY)]
        assets += [c for c in bpy.data.collections if c.get(AVALON_PROPERTY)]
        for asset in assets:
            if asset.get(AVALON_PROPERTY).get('libpath') == libpath:
                count += 1

        if isinstance(asset_group, bpy.types.Collection):
            self._remove(asset_group)
            bpy.data.collections.remove(asset_group)
        else:
            bpy.data.objects.remove(asset_group)

        # If it is the last object to use that library, remove it
        if count == 1:
            library = bpy.data.libraries.get(bpy.path.basename(libpath))
            bpy.data.libraries.remove(library)

        return True
