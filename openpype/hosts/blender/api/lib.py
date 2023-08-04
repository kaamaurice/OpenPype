from itertools import chain
import os
from pathlib import Path
import shutil
import traceback
import importlib
import contextlib
from typing import Dict, Iterable, Iterator, List, Set, Tuple, Union

import bpy
import addon_utils
from openpype.hosts.blender.api.properties import OpenpypeContainer
from openpype.hosts.blender.api.utils import (
    AVALON_PROPERTY,
    BL_OUTLINER_TYPES,
    assign_loader_to_datablocks,
    build_op_basename,
    ensure_unique_name,
    get_instanced_collections,
)
from openpype.lib import Logger
from openpype.modules import ModulesManager
from openpype.lib import Logger
from openpype.pipeline.constants import AVALON_CONTAINER_ID
from openpype.pipeline import Anatomy, legacy_io, schema
from openpype.pipeline.template_data import (
    get_template_data,
)
from openpype.pipeline.workfile.path_resolving import (
    get_workfile_template_key,
    get_last_workfile_with_version,
)
from openpype.client.entities import (
    get_subsets,
    get_representations,
    get_last_version_by_subset_id,
    get_asset_by_name,
    get_project,
)

from . import pipeline

log = Logger.get_logger(__name__)

def add_datablocks_to_container(
    datablocks: List[bpy.types.ID],
    container: OpenpypeContainer
):
    """Add datablocks reference to container.

    Args:
        datablocks (List[bpy.types.ID]): List of datablocks to add.
        container (OpenpypeContainer): Container to add datablocks to.
    """
    for d in datablocks:
        d_ref = container.datablock_refs.add()
        d_ref.datablock = d


def create_container(
    name: str, datablocks: List[bpy.types.ID]
) -> OpenpypeContainer:
    """Create OpenPype container in scene with name and relevant datablocks.

    Args:
        name (str): Container's name
        datablocks (List[bpy.types.ID]): Datablocks included by the datablock

    Returns:
        OpenpypeContainer: Created container
    """
    # Ensure container name
    name = ensure_unique_name(
        name, bpy.context.window_manager.openpype_containers.keys()
    )

    container = bpy.context.window_manager.openpype_containers.add()
    container.name = name

    add_datablocks_to_container(datablocks, container)

    return container


def parse_container(
    container: Union[bpy.types.Collection, bpy.types.Object],
    validate: bool = True,
) -> Dict:
    """Return the container node's full container data.

    Args:
        container: A container node name.
        validate: turn the validation for the container on or off

    Returns:
        The container schema data for this container node.

    """
    data = read(container)

    # NOTE (kaamaurice): experimental for the internal Asset browser.
    if (
        not data
        and isinstance(container, bpy.types.Object)
        and container.is_instancer
        and container.instance_collection
    ):
        data.update(read(container.instance_collection))

    # Append transient data
    data["objectName"] = container.name

    if validate:
        schema.validate(data)

    return data


def get_user_links(
    users_datablocks: bpy.types.ID,
    types: Union[bpy.types.ID, Iterable[bpy.types.ID]] = None,
) -> Tuple[Set[bpy.types.ID], Set[bpy.types.ID]]:
    """Return all datablocks linked to the user datablock recursively.

    Args:
        user_datablock (bpy.types.ID): Datablock to get links from

    Returns:
        Tuple[Set[bpy.types.ID], Set[bpy.types.ID]]: Tuple of linked and not
    """
    # Put into iterable if not
    if types is not None and not isinstance(types, Iterable):
        types = (types,)

    # Get all datablocks from blend file
    all_datablocks = set()
    for datacol in dir(bpy.data):
        if not isinstance(
            getattr(bpy.data, datacol),
            bpy.types.bpy_prop_collection,
        ):
            continue
        all_datablocks.update(getattr(bpy.data, datacol))

    users_links = {}
    user_map = bpy.data.user_map(subset=all_datablocks)

    all_not_linked = user_map.keys()
    for user in users_datablocks:
        current_user_links = users_links.setdefault(user, {user})
        not_linked = set()
        for datablock in all_not_linked:
            # Substitute scene collection with scene
            if (
                isinstance(datablock, bpy.types.Collection)
                and datablock == bpy.context.scene.collection
            ):
                user = bpy.context.scene

            # Recursive search
            _recursive_collect_user_links(
                datablock,
                user,
                current_user_links,
                not_linked,
                user_map,
            )
        all_not_linked -= current_user_links

    # Filter datablocks by types
    if types:
        types = tuple(types)
        users_links = {
            user: {d for d in datablocks if isinstance(d, types)}
            for user, datablocks in users_links.items()
        }
        not_linked = {d for d in not_linked if isinstance(d, types)}

    return users_links, not_linked


def _recursive_collect_user_links(
    datablock: bpy.types.ID,
    target_user_datablock: bpy.types.ID,
    links: set,
    exclude: set,
    user_map: dict,
):
    """Collect recursively all datablocks linked to the user datablock.

    Args:
        datablock (bpy.types.ID): Datablock currently tested.
        target_user_datablock (bpy.types.ID): Datablock to get links from.
        links (set): Set of datablocks linked to the user datablock.
        exclude (set): Set of datablocks to exclude from search.
        user_map (dict): User map of all datablocks in blend file.
    """

    for user in user_map.get(datablock, []):
        # Check not self reference to avoid infinite loop
        if user == datablock:
            continue
        elif user == target_user_datablock:
            links.add(datablock)
        elif user not in links | exclude:
            _recursive_collect_user_links(
                user, target_user_datablock, links, exclude, user_map
            )

        # Add datablock to links if user is linked to target datablock
        if (
            user.get(AVALON_PROPERTY, {}).get("id") != AVALON_CONTAINER_ID
            and user in links
        ):
            links.add(datablock)
        else:
            exclude.add(datablock)


def update_scene_containers():
    """Reset containers in scene."""
    scene_collection = bpy.context.scene.collection

    # Reset containers
    bpy.context.window_manager.openpype_containers.clear()

    # Get container datablocks not already correctly created
    # (e.g collection duplication or linked by hand)
    # For outliner datablocks, they must be in current scene
    # Sorted by type to ensure high level entities are processed first
    datatype_order = {  # Lower is first
        bpy.types.Collection: 0,
        bpy.types.Object: 1,
    }
    all_instanced_collections = get_instanced_collections()
    containerized_datablocks = [
        datablock
        for datablock in sorted(
            lsattr("id", AVALON_CONTAINER_ID),
            key=lambda d: datatype_order.get(type(d), 10),
        )
        if not (
            isinstance(datablock, tuple(BL_OUTLINER_TYPES))
            and datablock
            not in set(scene_collection.all_objects)
            | set(scene_collection.children_recursive)
            | all_instanced_collections
        )
    ]

    containers_loaders = assign_loader_to_datablocks(containerized_datablocks)
    containers_datablocks = get_user_links(containerized_datablocks)[0]

    for entity, datablocks in containers_datablocks.items():
        # Get container metadata
        container_metadata = (
            entity.instance_collection
            if hasattr(entity, "instance_collection")
            and entity.instance_collection
            else entity
        ).get(AVALON_PROPERTY)

        # Create container and keep it
        container_name = build_op_basename(
            container_metadata.get("asset_name"),
            container_metadata.get("name"),
        )

        # Filter datablocks by loader types
        if loader := containers_loaders.get(entity):
            containers_datablocks[entity] = {
                datablock
                for datablock in datablocks
                if isinstance(datablock, tuple(loader.bl_types))
            }

        create_container(container_name, datablocks)
        # NOTE need to get it this way because memory could have changed
        # BUG: https://projects.blender.org/blender/blender/issues/105338
        container = bpy.context.window_manager.openpype_containers[-1]

        # Keep objectName for update/switch
        container_metadata["objectName"] = container.name
        # Transfer container metadata and keep original outliner entity
        container[AVALON_PROPERTY] = container_metadata
        container.library = (
            entity.override_library.reference.library
            if entity.override_library
            else entity.library
        )


def ls() -> Iterator:
    """List containers from active Blender scene.

    This is the host-equivalent of api.ls(), but instead of listing assets on
    disk, it lists assets already loaded in Blender; once loaded they are
    called containers.
    """
    update_scene_containers()

    # Parse containers
    return [
        parse_container(container)
        for container in bpy.context.window_manager.openpype_containers
    ]


def load_scripts(paths):
    """Copy of `load_scripts` from Blender's implementation.

    It is possible that this function will be changed in future and usage will
    be based on Blender version.
    """
    import bpy_types

    loaded_modules = set()

    previous_classes = [
        cls
        for cls in bpy.types.bpy_struct.__subclasses__()
    ]

    def register_module_call(mod):
        register = getattr(mod, "register", None)
        if register:
            try:
                register()
            except:
                traceback.print_exc()
        else:
            print("\nWarning! '%s' has no register function, "
                  "this is now a requirement for registerable scripts" %
                  mod.__file__)

    def unregister_module_call(mod):
        unregister = getattr(mod, "unregister", None)
        if unregister:
            try:
                unregister()
            except:
                traceback.print_exc()

    def test_reload(mod):
        # reloading this causes internal errors
        # because the classes from this module are stored internally
        # possibly to refresh internal references too but for now, best not to.
        if mod == bpy_types:
            return mod

        try:
            return importlib.reload(mod)
        except:
            traceback.print_exc()

    def test_register(mod):
        if mod:
            register_module_call(mod)
            bpy.utils._global_loaded_modules.append(mod.__name__)

    from bpy_restrict_state import RestrictBlend

    with RestrictBlend():
        for base_path in paths:
            for path_subdir in bpy.utils._script_module_dirs:
                path = os.path.join(base_path, path_subdir)
                if not os.path.isdir(path):
                    continue

                bpy.utils._sys_path_ensure_prepend(path)

                # Only add to 'sys.modules' unless this is 'startup'.
                if path_subdir != "startup":
                    continue
                for mod in bpy.utils.modules_from_path(path, loaded_modules):
                    test_register(mod)

    addons_paths = []
    for base_path in paths:
        addons_path = os.path.join(base_path, "addons")
        if not os.path.exists(addons_path):
            continue
        addons_paths.append(addons_path)
        addons_module_path = os.path.join(addons_path, "modules")
        if os.path.exists(addons_module_path):
            bpy.utils._sys_path_ensure_prepend(addons_module_path)

    if addons_paths:
        # Fake addons
        origin_paths = addon_utils.paths

        def new_paths():
            paths = origin_paths() + addons_paths
            return paths

        addon_utils.paths = new_paths
        addon_utils.modules_refresh()

    # load template (if set)
    if any(bpy.utils.app_template_paths()):
        import bl_app_template_utils
        bl_app_template_utils.reset(reload_scripts=False)
        del bl_app_template_utils

    for cls in bpy.types.bpy_struct.__subclasses__():
        if cls in previous_classes:
            continue
        if not getattr(cls, "is_registered", False):
            continue
        for subcls in cls.__subclasses__():
            if not subcls.is_registered:
                print(
                    "Warning, unregistered class: %s(%s)" %
                    (subcls.__name__, cls.__name__)
                )


def append_user_scripts():
    user_scripts = os.environ.get("OPENPYPE_BLENDER_USER_SCRIPTS")
    if not user_scripts:
        return

    try:
        load_scripts(user_scripts.split(os.pathsep))
    except Exception:
        print("Couldn't load user scripts \"{}\"".format(user_scripts))
        traceback.print_exc()


def imprint(node: bpy.types.bpy_struct_meta_idprop, data: Dict):
    r"""Write `data` to `node` as userDefined attributes

    Arguments:
        node: Long name of node
        data: Dictionary of key/value pairs

    Example:
        >>> import bpy
        >>> def compute():
        ...   return 6
        ...
        >>> bpy.ops.mesh.primitive_cube_add()
        >>> cube = bpy.context.view_layer.objects.active
        >>> imprint(cube, {
        ...   "regularString": "myFamily",
        ...   "computedValue": lambda: compute()
        ... })
        ...
        >>> cube['avalon']['computedValue']
        6
    """

    imprint_data = dict()

    for key, value in data.items():
        if value is None:
            continue

        if callable(value):
            # Support values evaluated at imprint
            value = value()

        if not isinstance(value, (int, float, bool, str, list)):
            raise TypeError(f"Unsupported type: {type(value)}")

        imprint_data[key] = value

    pipeline.metadata_update(node, imprint_data)


def lsattr(attr: str,  # TODO might be useless now
           value: Union[str, int, bool, List, Dict, None] = None) -> List:
    r"""Return nodes matching `attr` and `value`

    Arguments:
        attr: Name of Blender property
        value: Value of attribute. If none
            is provided, return all nodes with this attribute.

    Example:
        >>> lsattr("id", "myId")
        ...   [bpy.data.objects["myNode"]
        >>> lsattr("id")
        ...   [bpy.data.objects["myNode"], bpy.data.objects["myOtherNode"]]

    Returns:
        list
    """

    return lsattrs({attr: value})


def lsattrs(attrs: Dict) -> List:  # TODO might be useless now
    r"""Return nodes with the given attribute(s).

    Arguments:
        attrs: Name and value pairs of expected matches

    Example:
        >>> lsattrs({"age": 5})  # Return nodes with an `age` of 5
        # Return nodes with both `age` and `color` of 5 and blue
        >>> lsattrs({"age": 5, "color": "blue"})

    Returns a list.

    """

    # For now return all objects, not filtered by scene/collection/view_layer.
    matches = set()
    for coll in dir(bpy.data):
        if not isinstance(
                getattr(bpy.data, coll),
                bpy.types.bpy_prop_collection,
        ):
            continue
        for node in getattr(bpy.data, coll):
            for attr, value in attrs.items():
                avalon_prop = node.get(pipeline.AVALON_PROPERTY)
                if not avalon_prop:
                    continue
                if (avalon_prop.get(attr)
                        and (value is None or avalon_prop.get(attr) == value)):
                    matches.add(node)
    return list(matches)


def read(node: bpy.types.bpy_struct_meta_idprop):
    """Return user-defined attributes from `node`"""

    data = node[pipeline.AVALON_PROPERTY]

    # Ignore hidden/internal data
    data = {
        key: value
        for key, value in data.items() if not key.startswith("_")
    }

    return data


def get_selection() -> List[bpy.types.Object]:
    """Return the selected objects from the current scene."""
    return [obj for obj in bpy.context.scene.objects if obj.select_get()]


@contextlib.contextmanager
def maintained_selection():
    r"""Maintain selection during context

    Example:
        >>> with maintained_selection():
        ...     # Modify selection
        ...     bpy.ops.object.select_all(action='DESELECT')
        >>> # Selection restored
    """

    previous_selection = get_selection()
    previous_active = bpy.context.view_layer.objects.active
    try:
        yield
    finally:
        # Clear the selection
        for node in get_selection():
            node.select_set(state=False)
        if previous_selection:
            for node in previous_selection:
                try:
                    node.select_set(state=True)
                except ReferenceError:
                    # This could happen if a selected node was deleted during
                    # the context.
                    log.exception("Failed to reselect")
                    continue
        try:
            bpy.context.view_layer.objects.active = previous_active
        except ReferenceError:
            # This could happen if the active node was deleted during the
            # context.
            log.exception("Failed to set active object.")


@contextlib.contextmanager
def maintained_visibility():
    """Maintain visibility during context."""

    previous_hidden_objects = [
        obj for obj in bpy.context.scene.objects if obj.hide_get()
    ]
    previous_hidden_collections = [
        col for col in bpy.context.scene.collection.children_recursive
        if col.hide_viewport
    ]
    previous_hidden_layer_collection = [
        col for col in bpy.context.view_layer.layer_collection.children
        if col.hide_viewport
    ]
    try:
        yield
    finally:
        for obj in bpy.context.scene.objects:
            obj.hide_set(obj in previous_hidden_objects)
        for col in bpy.context.scene.collection.children_recursive:
            col.hide_viewport = col in previous_hidden_collections
        for col in bpy.context.view_layer.layer_collection.children:
            col.hide_viewport = col in previous_hidden_layer_collection


@contextlib.contextmanager
def maintained_time():
    """Maintain current frame during context."""
    current_time = bpy.context.scene.frame_current
    try:
        yield
    finally:
        bpy.context.scene.frame_current = current_time


def download_last_workfile() -> str:
    """Download last workfile and return its path.

    Returns:
        str: Path to last workfile.
    """
    from openpype.modules.sync_server.sync_server import (
        download_last_published_workfile,
    )

    sync_server = ModulesManager().get("sync_server")
    if not sync_server or not sync_server.enabled:
        raise RuntimeError("Sync server module is not enabled or available")

    session = legacy_io.Session
    project_name = session.get("AVALON_PROJECT")
    task_name = session.get("AVALON_TASK")
    asset_name = session.get("AVALON_ASSET")
    anatomy = Anatomy(project_name)
    asset_doc = get_asset_by_name(
        project_name,
        session.get("AVALON_ASSET"),
    )
    family = "workfile"

    filtered_subsets = [
        subset
        for subset in get_subsets(
            project_name,
            asset_ids=[asset_doc["_id"]],
            fields=["_id", "name", "data.family", "data.families"],
        )
        if (
            subset["data"].get("family") == family
            # Legacy compatibility
            or family in subset["data"].get("families", {})
        )
    ]
    if not filtered_subsets:
        raise RuntimeError(
            "Not any subset for asset '{}' with id '{}'".format(
                asset_doc["name"], asset_doc["_id"]
            )
        )

    # Match subset wich has `task_name` in its name
    low_task_name = task_name.lower()
    if len(filtered_subsets) > 1:
        for subset in filtered_subsets:
            if low_task_name in subset["name"].lower():
                subset_id = subset["_id"]  # What if none is found?
    else:
        subset_id = filtered_subsets[0]["_id"]

    if subset_id is None:
        print(
            f"Not any matched subset for task '{task_name}'"
            f" of '{asset_name}'"
        )
        return

    # Get workfile representation
    last_version_doc = get_last_version_by_subset_id(
        project_name, subset_id, fields=["_id", "name", "data"]
    )
    if not last_version_doc:
        print("Subset does not have any version")
        return

    workfile_representations = list(
        get_representations(
            project_name,
            context_filters={
                "asset": asset_name,
                "family": "workfile",
                "task": {"name": task_name},
            },
        )
    )

    if not workfile_representations:
        raise RuntimeError(
            f"No published workfile for task {task_name} and host blender."
        )

    workfile_representation = max(
        filter(
            lambda r: r["context"].get("version"),
            workfile_representations,
        ),
        key=lambda r: r["context"]["version"],
    )
    if not workfile_representation:
        raise RuntimeError(
            "No published workfile for task " f"'{task_name}' and host blender"
        )

    # Get workfile template data
    workfile_data = get_template_data(
        get_project(project_name, inactive=False),
        asset_doc,
        task_name,
        "blender",
    )

    # Get workfile version
    workfile_data["version"] = (
        get_last_workfile_with_version(
            Path(bpy.data.filepath).parent.as_posix(),
            anatomy.templates[
                get_workfile_template_key(task_name, "blender", project_name)
            ]["file"],
            workfile_data,
            ["blend"],
        )[1]
        + 1
    )
    workfile_data["ext"] = "blend"

    # Get local workfile path
    local_workfile_path = anatomy.format(workfile_data)[
        get_workfile_template_key(task_name, "blender", project_name)
    ]["path"]

    # Download and get last workfile
    last_published_workfile_path = download_last_published_workfile(
        "blender",
        project_name,
        task_name,
        workfile_representation,
        int(
            (
                sync_server.sync_project_settings[project_name]["config"][
                    "retry_cnt"
                ]
            )
        ),
        anatomy=anatomy,
    )

    if (
        not last_published_workfile_path
        or not Path(last_published_workfile_path).exists()
    ):
        raise OSError("Failed to download last published workfile")

    # Download and copy last published workfile to local workfile path
    shutil.copy(
        last_published_workfile_path,
        local_workfile_path,
    )

    return local_workfile_path, last_version_doc["data"]["time"]
