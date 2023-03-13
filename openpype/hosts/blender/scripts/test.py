import bpy

from openpype.hosts.blender.scripts.build_workfile import build_workfile
from openpype.pipeline import legacy_io

legacy_io.Session["AVALON_PROJECT"] = "WoollyWoolly"
legacy_io.Session["AVALON_ASSET"] = "ep108_sq107_e108_sh117"
legacy_io.Session["AVALON_TASK"] = "Layout"

build_workfile()

if bpy.data.filepath:
    bpy.ops.save_mainfile()