"""Create an animation asset."""

from openpype.hosts.blender.api import plugin


class CreateAction(plugin.Creator):
    """Action output for character rigs"""

    name = "actionMain"
    label = "Action"
    family = "action"
    icon = "male"
