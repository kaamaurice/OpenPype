import bpy
import pyblish.api

from openpype.hosts.blender.api.lock import (
    get_lock_system_enabled,
    subset_is_locked_and_lock_is_valid,
)


class ValidateFileNotLocked(pyblish.api.ContextPlugin):
    """Subset must not be locked in database."""

    order = pyblish.api.ValidatorOrder
    hosts = ["blender"]
    label = "Validate File Not Locked"

    def process(self, context):
        """ContextPlugin processing method.

        Args:
            context (pyblish.api.Context): Context with which to process
        """
        if not get_lock_system_enabled():
            return

        # Use stored attribute as it's the lock state when
        # the scene was opened
        if hasattr(context.window_manager, "subset_is_locked"):
            lock = context.window_manager.subset_is_locked

        # Fallback on the check function otherwise
        # but if the file was unlocked between the opening and the publish,
        # the publish will be allowed, which can lead to invalid data
        else:
            lock = subset_is_locked_and_lock_is_valid()

        if lock:
            raise RuntimeError(
                "You can't publish a file that was locked by someone else!"
            )
