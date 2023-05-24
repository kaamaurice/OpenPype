"""Make all paths relative."""

from pathlib import Path
from itertools import chain
import sys
import bpy
from openpype.hosts.blender.api.utils import ERROR_MAGIC

from openpype.lib.log import Logger

if __name__ == "__main__":
    log = Logger().get_logger()
    log.debug(
        f"Blend file | All paths converted to relative: {bpy.data.filepath}"
    )
    errors = []
    # Resolve path from source filepath with the relative filepath
    for datablock in chain(bpy.data.libraries, bpy.data.images):
        try:
            if (
                datablock
                and not datablock.is_library_indirect
                and not datablock.filepath.startswith("//")
            ):
                datablock.filepath = bpy.path.relpath(
                    str(Path(datablock.filepath).resolve()),
                    start=str(Path(bpy.data.filepath).parent.resolve()),
                )
                raise Exception("blabla")
        # except (RuntimeError, ReferenceError, ValueError, OSError) as e:
            
        except BaseException as e:
            errors.append(e)
    
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    
    # Raise errors
    if errors:
        raise RuntimeError(
            f"{ERROR_MAGIC}{errors}{ERROR_MAGIC}"
        )
