"""Load an asset in Blender from a FBX file."""

from openpype.hosts.blender.api import plugin


class FbxModelLoader(plugin.AssetLoader):
    """Load FBX models.

    Stores the imported asset in a collection named after the asset.
    """

    families = ["model", "rig"]
    representations = ["fbx"]

    label = "Load FBX"
    icon = "download"
    color = "orange"
    order = 4

    def _process(self, libpath, asset_group):
        self._load_fbx(libpath, asset_group)

