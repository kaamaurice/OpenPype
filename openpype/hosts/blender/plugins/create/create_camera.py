"""Create a camera asset."""

from openpype.hosts.blender.api import plugin


class CreateCamera(plugin.Creator):
    """Polygonal static geometry"""

    name = "cameraMain"
    label = "Camera"
    family = "camera"
    icon = "video-camera"
