"""Shared functionality for pipeline plugins for Blender."""

from pathlib import Path
from typing import Dict, Optional

import bpy

from openpype.pipeline import (
    LegacyCreator,
    LoaderPlugin,
    AVALON_CONTAINER_ID,
)
from openpype.pipeline.context_tools import get_current_task_name
from .pipeline import AVALON_PROPERTY
from .ops import (
    MainThreadItem,
    execute_in_main_thread
)
from .lib import (
    imprint,
    get_selection
)

VALID_EXTENSIONS = [".blend", ".json", ".abc", ".fbx"]


def get_asset_name(
    asset: str, subset: str, namespace: Optional[str] = None
) -> str:
    """Return a consistent name for an asset."""
    name = f"{asset}"
    if namespace:
        name = f"{name}_{namespace}"
    name = f"{name}_{subset}"
    return name


def get_unique_number(
    asset: str, subset: str
) -> str:
    """Return a unique number based on the asset name."""
    container_names = [c.name for c in bpy.data.collections]
    count = 1
    name = f"{asset}_{count:0>2}_{subset}"
    while name in container_names:
        count += 1
        name = f"{asset}_{count:0>2}_{subset}"
    return f"{count:0>2}"


def prepare_data(data, container_name=None):
    name = data.name
    local_data = data.make_local()
    if container_name:
        local_data.name = f"{container_name}:{name}"
    else:
        local_data.name = f"{name}"
    return local_data


def create_blender_context(active: Optional[bpy.types.Object] = None,
                           selected: Optional[bpy.types.Object] = None,
                           window: Optional[bpy.types.Window] = None):
    """Create a new Blender context. If an object is passed as
    parameter, it is set as selected and active.
    """

    if not isinstance(selected, list):
        selected = [selected]

    override_context = bpy.context.copy()

    windows = [window] if window else bpy.context.window_manager.windows

    for win in windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override_context['window'] = win
                        override_context['screen'] = win.screen
                        override_context['area'] = area
                        override_context['region'] = region
                        override_context['scene'] = bpy.context.scene
                        override_context['active_object'] = active
                        override_context['selected_objects'] = selected
                        return override_context
    raise Exception("Could not create a custom Blender context.")


def get_parent_collection(collection):
    """Get the parent of the input collection"""
    check_list = [bpy.context.scene.collection]

    for c in check_list:
        if collection.name in c.children.keys():
            return c
        check_list.extend(c.children)

    return None


def get_local_collection_with_name(name):
    for collection in bpy.data.collections:
        if collection.name == name and collection.library is None:
            return collection
    return None


def deselect_all():
    """Deselect all objects in the scene.

    Blender gives context error if trying to deselect object that it isn't
    in object mode.
    """
    modes = []
    active = bpy.context.view_layer.objects.active

    for obj in bpy.data.objects:
        if obj.mode != 'OBJECT':
            modes.append((obj, obj.mode))
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')

    for p in modes:
        bpy.context.view_layer.objects.active = p[0]
        bpy.ops.object.mode_set(mode=p[1])

    bpy.context.view_layer.objects.active = active


class Creator(LegacyCreator):
    """Base class for Creator plug-ins."""
    defaults = ['Main']

    def __init__(self, *args, **kwargs):
        super(Creator, self).__init__(*args, **kwargs)
        self.data["task"] = get_current_task_name()

    def process(self):
        """ Run the creator on Blender main thread"""
        mti = MainThreadItem(self._process)
        execute_in_main_thread(mti)

    def _process(self):
        collection = bpy.data.collections.new(name=self.data["subset"])
        collection.color_tag = "COLOR_07"
        bpy.context.scene.collection.children.link(collection)
        imprint(collection, self.data)

        if (self.options or {}).get("useSelection"):
            for obj in get_selection():
                collection.objects.link(obj)
        elif (self.options or {}).get("asset_group"):
            obj = self.options.get("asset_group")
            collection.objects.link(obj)

        return collection


class Loader(LoaderPlugin):
    """Base class for Loader plug-ins."""

    hosts = ["blender"]

    def exec_load(
        self,
        context: dict,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        options: Optional[Dict] = None,
    ):
        """Must be implemented by a sub-class"""
        raise NotImplementedError("Must be implemented by a sub-class")

    def load(
        self,
        context: dict,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        options: Optional[Dict] = None,
    ):
        """ Run the loader on Blender main thread"""
        mti = MainThreadItem(self.exec_load, context, name, namespace, options)
        execute_in_main_thread(mti)
        return mti

    def exec_update(self, container: Dict, representation: Dict):
        """Must be implemented by a sub-class"""
        raise NotImplementedError("Must be implemented by a sub-class")

    def update(self, container: Dict, representation: Dict):
        """ Run the update on Blender main thread"""
        mti = MainThreadItem(self.exec_update, container, representation)
        execute_in_main_thread(mti)
        return mti

    def exec_remove(self, container: Dict) -> bool:
        """Must be implemented by a sub-class"""
        raise NotImplementedError("Must be implemented by a sub-class")

    def remove(self, container: Dict) -> bool:
        """ Run the remove on Blender main thread"""
        mti = MainThreadItem(self.exec_remove, container)
        execute_in_main_thread(mti)
        return mti


class AssetLoader(LoaderPlugin):
    """A basic AssetLoader for Blender

    This will implement the basic logic for linking/appending assets
    as collection into another Blender scene.

    The abstract methods should be implemented by a sub-class, because
    it's different for different types (e.g. model, rig, animation,
    etc.).
    """

    def load_asset(self,
                      context: dict,
                      name: str,
                      namespace: Optional[str] = None,
                      options: Optional[Dict] = None):
        """Must be implemented by a sub-class"""
        raise NotImplementedError("Must be implemented by a sub-class")

    def exec_load(
        self,
        context: dict,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> Optional[bpy.types.Collection]:
        """Load asset via database.

        Arguments:
            context: Full parenthood of representation to load
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            options: Additional settings dictionary

        Returns:
            (bpy.types.Collection): The root collection.
        """
        assert Path(self.fname).exists(), f"{self.fname} doesn't exist."

        libpath = self.fname
        asset = context["asset"]["name"]
        subset = context["subset"]["name"]
        unique_number = get_unique_number(asset, subset)
        namespace = namespace or f"{asset}_{unique_number}"
        asset_group_name = get_asset_name(asset, subset, unique_number)
        name = name or asset_group_name

        asset_members = self.load_asset(
            context=context,
            name=name,
            namespace=namespace,
            options=options,
        )

        if not asset_members:
            return None

        asset_group = bpy.data.collections.new(name=asset_group_name)
        asset_group.color_tag = "COLOR_05"
        bpy.context.scene.collection.children.link(asset_group)

        for member in asset_members:
            if isinstance(member, bpy.types.Object):
                asset_group.objects.link(member)
            elif isinstance(member, bpy.types.Collection):
                asset_group.children.link(member)

        asset_group["members"] = asset_members

        asset_group[AVALON_PROPERTY] = {
            "schema": "openpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(context["representation"]["_id"]),
            "libpath": libpath,
            "asset_name": asset,
            "parent": str(context["representation"]["parent"]),
            "family": context["representation"]["context"]["family"],
            "objectName": asset_group_name
        }

        self[:] = asset_members
        return asset_group

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (dict): Container to remove.

        Returns:
            (bool): Whether the container was deleted.
        """
        asset_group = self._get_asset_group_container(container)

        if not asset_group:
            return False

        remove_container(asset_group)
        orphans_purge()

        return True
