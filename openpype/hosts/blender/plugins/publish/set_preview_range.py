import pyblish.api
import bpy


class SetPreviewRange(pyblish.api.ContextPlugin):
    """Set preview range to `True` if it has been deactivated."""

    order = pyblish.api.IntegratorOrder + 0.02
    hosts = ['blender']
    families = ['animation']
    label = 'Set Preview Range'
    optional = True

    def process(self, context):
        scene = bpy.context.scene
        if scene.has_preview_range:
            scene.use_preview_range = True

        del bpy.types.Scene.has_preview_range
