import bpy

import pyblish.api

from openpype.pipeline.publish import get_errored_instances_from_context


class SelectInvalidAction(pyblish.api.Action):
    """Select invalid objects in Blender when a publish plug-in failed."""
    label = "Select Invalid"
    on = "failed"
    icon = "search"

    def process(self, context, plugin):
        errored_instances = get_errored_instances_from_context(context)
        instances = pyblish.api.instances_by_plugin(errored_instances, plugin)
        
        # Get the invalid nodes for the plug-ins
        self.log.info("Finding invalid nodes...")
        invalid = list()
        for instance in instances:
            invalid_nodes = plugin.get_invalid(instance)
            if invalid_nodes:
                if isinstance(invalid_nodes, (list, tuple)):
                    invalid.extend(invalid_nodes)
                else:
                    invalid_nodes.append(invalid)

        # Get selectable objects from invalid nodes.
        invalid_objects = set()
        for node in invalid_nodes:
            if isinstance(node, bpy.types.Object):
                invalid_objects.add(node)
            elif isinstance(node, bpy.types.Collection):
                invalid_objects.update(node.all_objects)

        if not invalid_objects:
            self.log.warning(
                "Failed plug-in doesn't have any selectable objects."
            )

        bpy.ops.object.select_all(action='DESELECT')

        # Make sure every node is only processed once
        invalid = list(invalid_objects)
        if not invalid:
            self.log.info("No invalid nodes found.")
            return

        invalid_names = [obj.name for obj in invalid]
        self.log.info(
            "Selecting invalid objects: %s", ", ".join(invalid_names)
        )
        # Select the objects and also make the last one the active object.
        for obj in invalid:
            obj.select_set(True)

        bpy.context.view_layer.objects.active = invalid[-1]
