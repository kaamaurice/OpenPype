import os

import bpy
from bson.objectid import ObjectId

from openpype.pipeline import (
    publish,
    discover_loader_plugins,
    AVALON_CONTAINER_ID,
)
from openpype.pipeline.load.utils import loaders_from_repre_context
from openpype.hosts.blender.api import plugin
from openpype.hosts.blender.api.pipeline import (
    metadata_update,
    AVALON_PROPERTY,
)


class ExtractBlend(publish.Extractor):
    """Extract a blend file."""

    label = "Extract Blend"
    hosts = ["blender"]
    families = ["model", "camera", "rig", "action", "layout"]
    optional = True

    def process(self, instance):
        # Define extract output file path

        stagingdir = self.staging_dir(instance)
        filename = f"{instance.name}.blend"
        filepath = os.path.join(stagingdir, filename)

        # Perform extraction
        self.log.info("Performing extraction..")

        plugin.deselect_all()

        data_blocks = set()
        objects = set()

        # Adding all members of the instance to data blocks that will be
        # written into the blender library.
        for member in instance:
            data_blocks.add(member)
            # Get reference from override library.
            if member.override_library and member.override_library.reference:
                data_blocks.add(member.override_library.reference)
            # Store objects to pack images from their materials.
            if isinstance(member, bpy.types.Object):
                objects.add(member)

        # Store instance metadata
        instance_collection = instance[-1]
        instance_metadata = instance_collection[AVALON_PROPERTY].to_dict()
        instance_collection[AVALON_PROPERTY] = dict()

        # Add container metadata to collection
        metadata_update(
            instance_collection,
            {
                "schema": "openpype:container-2.0",
                "id": AVALON_CONTAINER_ID,
                "name": instance_metadata["subset"],
                "asset_name": instance_metadata["asset"],
                "parent": str(instance.data["assetEntity"]["parent"]),
                "family": instance.data["family"],
            },
        )

        bpy.data.libraries.write(
            filepath,
            data_blocks,
            path_remap="ABSOLUTE",
            fake_user=True,
        )

        # restor instance metadata
        instance_collection[AVALON_PROPERTY] = instance_metadata

        # Create representation dict
        representation = {
            "name": "blend",
            "ext": "blend",
            "files": filename,
            "stagingDir": stagingdir,
        }
        instance.data.setdefault("representations", [])
        instance.data["representations"].append(representation)

        self.log.info(
            f"Extracted instance '{instance.name}' to: {representation}"
        )
