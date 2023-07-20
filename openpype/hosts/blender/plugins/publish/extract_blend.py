from pathlib import Path
from typing import List, Set, Tuple

import bpy

from openpype.pipeline import publish
from openpype.lib import source_hash
from openpype.hosts.blender.api import plugin, get_compress_setting
from openpype.settings.lib import get_project_settings


class ExtractBlend(publish.Extractor):
    """Extract the scene as blend file."""

    label = "Extract Blend"
    hosts = ["blender"]
    families = ["model", "camera", "rig", "layout", "setdress"]
    optional = True

    pack_images = False

    def process(self, instance):
        # Define extract output file path
        stagingdir = self.staging_dir(instance)
        filename = f"{instance.name}.blend"
        filepath = Path(stagingdir, filename)

        # If paths management, make paths absolute before saving
        project_name = instance.data["projectEntity"]["name"]
        project_settings = get_project_settings(project_name)
        host_name = instance.context.data["hostName"]
        host_settings = project_settings.get(host_name)
        if host_settings.get("general", {}).get("use_paths_management"):
            bpy.ops.file.make_paths_absolute()

        # Perform extraction
        self.log.info("Performing extraction..")

        # Make camera visible in viewport
        camera = bpy.context.scene.camera
        if camera:
            is_camera_hidden_viewport = camera.hide_viewport
            camera.hide_viewport = False
        else:
            is_camera_hidden_viewport = False

        # Set object mode if some objects are not.
        not_object_mode_objs = [
            obj
            for obj in bpy.context.scene.objects
            if obj.mode != "OBJECT"
        ]
        if not_object_mode_objs:
            with plugin.context_override(
                active=not_object_mode_objs[0],
                selected=not_object_mode_objs,
            ):
                bpy.ops.object.mode_set()

        # Set camera hide in viewport back to its original value
        if is_camera_hidden_viewport:
            camera.hide_viewport = True

        plugin.deselect_all()

        data_blocks = set(instance)

        # Substitute objects by their collections to avoid data duplication
        collections = set(plugin.get_collections_by_objects(data_blocks))
        if collections:
            data_blocks.update(collections)

        # Get images used by datablocks
        used_images = self._get_used_images(data_blocks)

        # Pack used images in the blend files.
        packed_images = set()
        if self.pack_images:
            for image in used_images:
                if not image.packed_file and image.source != "GENERATED":
                    packed_images.add((image, image.is_dirty))
                    image.pack()

        # process resources
        transfers, hashes, remapped = self._process_resources(
            instance,
            set(used_images) | set(bpy.data.texts) | set(bpy.data.sounds),
        )

        self._write_data(filepath, data_blocks)

        # restor packed images.
        for image, is_dirty in packed_images:
            if not image.filepath:
                unpack_method = "REMOVE"
            elif is_dirty:
                unpack_method = "WRITE_ORIGINAL"
            else:
                unpack_method = "USE_ORIGINAL"
            image.unpack(method=unpack_method)

        plugin.deselect_all()

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

        # Restore remapped path
        for image, sourcepath in remapped:
            image.filepath = str(sourcepath)

        # Set up the resources transfers/links for the integrator
        instance.data.setdefault("transfers", [])
        instance.data["transfers"].extend(transfers)

        # Source hash for the textures
        instance.data.setdefault("sourceHashes", [])
        instance.data["sourceHashes"] = hashes

    def _write_data(self, filepath: Path, datablocks: Set[bpy.types.ID]):
        """Write data to filepath.

        Args:
            filepath (Path): Filepath to write data to.
            datablocks (Set[bpy.types.ID]): Datablocks to write.
        """
        bpy.data.libraries.write(
            filepath.as_posix(),
            datablocks,
            fake_user=True,
            compress=get_compress_setting(),
        )

    def _get_used_images(
        self, datablocks: Set[bpy.types.ID] = None
    ) -> Set[bpy.types.Image]:
        """Get images used by the datablocks.

        Args:
            datablocks (Set[bpy.types.ID], optional): Datablocks to get images
                from. Defaults to None.

        Returns:
            Set[bpy.types.Image]: Images used.
        """
        return {
            img
            for img, users in bpy.data.user_map(subset=bpy.data.images).items()
            if users & datablocks
        }

    def _process_resources(
        self, instance: dict, resources: set
    ) -> Tuple[List[Tuple[str, str]], dict, Set[Tuple[bpy.types.ID, Path]]]:
        """Extract the resources to transfer, copy them to the resource
        directory and remap the node paths.

        Args:
            instance (dict): Instance with resources
            resources (set): Blender resources to publish

        Returns:
            Tuple[Tuple[str, str], dict, Set[Tuple[bpy.types.ID, Path]]]:
                (Files to copy and transfer with published blend,
                source hashes for later file optim,
                remapped filepath with source file path)
        """
        # Process the resource files
        transfers = []
        hashes = {}
        remapped = set()
        for resource in resources:
            # Skip resource from library or internal
            if resource.library or not resource.filepath:
                continue
            # Skip generated or packed images
            if (
                isinstance(resource, bpy.types.Image)
                and (
                    not resource.source in {"FILE", "SEQUENCE", "MOVIE"}
                    or resource.packed_file
                )
            ):
                continue

            # Get source and destination paths
            sourcepath = resource.filepath
            destination = Path(
                instance.data["resourcesDir"], Path(sourcepath).name
            )

            transfers.append((sourcepath, destination.as_posix()))
            self.log.info(f"file will be copied {sourcepath} -> {destination}")

            # Store the hashes from hash to destination to include in the
            # database
            # NOTE Keep source hash system in case HARDLINK system works again
            resource_hash = source_hash(sourcepath)
            hashes[resource_hash] = destination.as_posix()

            # Remap source file to resources directory
            resource.filepath = bpy.path.relpath(
                destination.as_posix(), start=instance.data["publishDir"]
            )

            # Keep remapped to restore after publishing
            remapped.add((resource, sourcepath))

        self.log.info("Finished remapping destinations...")

        return transfers, hashes, remapped
