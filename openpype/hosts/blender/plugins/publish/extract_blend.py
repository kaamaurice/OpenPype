import os

import bpy
from avalon import api

import openpype.api
from openpype.hosts.blender.api import plugin


class ExtractBlend(openpype.api.Extractor):
    """Extract a blend file."""

    label = "Extract Blend"
    hosts = ["blender"]
    families = ["model", "camera", "rig", "action", "layout"]
    optional = True

    def _set_original_name_property(self, object):
        object["original_name"] = object.name
        object.property_overridable_library_set('["original_name"]', True)

    def _set_namespace_property(self, object, container):
        object["namespace"] = container.name
        object.property_overridable_library_set('["namespace"]', True)

    def process(self, instance):
        # Define extract output file path

        stagingdir = self.staging_dir(instance)
        filename = f"{instance.name}.blend"
        filepath = os.path.join(stagingdir, filename)

        # Perform extraction
        self.log.info("Performing extraction..")

        plugin.remove_orphan_datablocks()
        # Get instance collection
        container = bpy.data.collections[instance.name]
        objects = plugin.get_all_objects_in_collection(container)
        collections = plugin.get_all_collections_in_collection(container)

        plugin.remove_orphan_datablocks()
        plugin.remove_namespace_for_objects_container(container)

        # define if objects have namspace by task
        has_namespace = (
            api.Session["AVALON_TASK"]
            in [
                "Rigging",
                "Modeling",
            ]
            or container["avalon"].get("family") == "camera"
        )

        self._set_original_name_property(container)
        if has_namespace:
            self._set_namespace_property(container, container)

        for collection in collections:
            # remove the namespace if exists
            self._set_original_name_property(collection)
            if has_namespace:
                self._set_namespace_property(collection, container)

        # Create data block set
        data_blocks = set()
        data_blocks.add(container)

        for obj in objects:
            data_blocks.add(obj)

            # if doesn't exist create the custom property original_name
            self._set_original_name_property(obj)
            if obj.type != "EMPTY":
                if obj.data is not None:
                    self._set_original_name_property(obj.data)
            if has_namespace:
                self._set_namespace_property(obj, container)
                if obj.type != "EMPTY":
                    if obj.data is not None:
                        self._set_namespace_property(obj.data, container)

            # Pack used images in the blend files.
            if obj.type == 'MESH':
                for material_slot in obj.material_slots:
                    mat = material_slot.material
                    if mat and mat.use_nodes:
                        tree = mat.node_tree
                        if tree.type == 'SHADER':
                            for node in tree.nodes:
                                if node.bl_idname == 'ShaderNodeTexImage':
                                    if node.image:
                                        node.image.pack()

        # Write the .blend library with data_blocks collected
        bpy.data.libraries.write(filepath, data_blocks)

        # Create and set representation to the instance data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'blend',
            'ext': 'blend',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        self.log.info("Extracted instance '%s' to: %s",
                      instance.name, representation)
