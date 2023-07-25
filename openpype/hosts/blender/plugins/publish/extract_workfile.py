from pathlib import Path
from typing import List, Set, Tuple

import pyblish
import bpy
from openpype.hosts.blender.plugins.publish import extract_blend

from openpype.hosts.blender.api import get_compress_setting


class ExtractWorkfile(extract_blend.ExtractBlend):
    """Extract the scene as workfile blend file."""

    label = "Extract workfile"
    hosts = ["blender"]
    families = ["workfile"]

    # Run first
    order = pyblish.api.ExtractorOrder - 0.1

    def _write_data(self, filepath: Path, *args):
        """Override to save mainfile with all data.

        Args:
            filepath (Path): Path to save mainfile to.
        """
        bpy.ops.wm.save_as_mainfile(
            filepath=filepath.as_posix(),
            compress=get_compress_setting(),
            relative_remap=False,
            copy=True,
        )

    def _get_used_images(self, *args) -> Set[bpy.types.Image]:
        """Override to return all images.

        Returns:
            Set[bpy.types.Image]: All images in blend file
        """
        return set(bpy.data.images)

    def _process_resources(
        self, instance: dict, resources: set
    ) -> Tuple[List[Tuple[str, str]], dict, Set[Tuple[bpy.types.ID, Path]]]:
        """Override to add texts and sounds to resources.

        Args:
            instance (dict): Instance with resources
            resources (set): Blender resources to publish

        Returns:
            Tuple[Tuple[str, str], dict, Set[Tuple[bpy.types.ID, Path]]]:
                (Files to copy and transfer with published blend,
                source hashes for later file optim,
                remapped filepath with source file path)
        """

        return super()._process_resources(
            instance, resources | set(bpy.data.texts) | set(bpy.data.sounds)
        )
