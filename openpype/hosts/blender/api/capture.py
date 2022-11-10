"""Blender Capture

Playblasting with independent viewport, camera and display options

"""
from pathlib import Path
import contextlib
import bpy

from .lib import maintained_time, maintained_selection, maintained_visibility
from .plugin import deselect_all, context_override


def capture(
    camera=None,
    width=None,
    height=None,
    filepath=None,
    start_frame=None,
    end_frame=None,
    step_frame=None,
    sound=None,
    isolate=None,
    focus=None,
    maintain_aspect_ratio=True,
    overwrite=False,
    image_settings=None,
    display_options=None,
):
    """Playblast in an independent windows

    Arguments:
        camera (str, optional): Name of camera, defaults to "Camera"
        width (int, optional): Width of output in pixels
        height (int, optional): Height of output in pixels
        filepath (str, optional): Name of output file path. Defaults to current
            render output path.
        start_frame (int, optional): Defaults to current start frame.
        end_frame (int, optional): Defaults to current end frame.
        step_frame (int, optional): Defaults to 1.
        sound (str, optional):  Specify the sound node to be used during
            playblast. When None (default) no sound will be used.
        isolate (list): List of nodes to isolate upon capturing
        maintain_aspect_ratio (bool, optional): Modify height in order to
            maintain aspect ratio.
        overwrite (bool, optional): Whether or not to overwrite if file
            already exists. If disabled and file exists and error will be
            raised.
        image_settings (dict, optional): Supplied image settings for render,
            using `ImageSettings`
        display_options (dict, optional): Supplied display options for render
    """

    scene = bpy.context.scene
    camera = camera or "Camera"

    # Ensure camera exists.
    if camera not in scene.objects and camera != "AUTO":
        raise RuntimeError(f"Camera does not exist: {camera}")

    # Ensure resolution.
    if width and height:
        maintain_aspect_ratio = False
    width = width or scene.render.resolution_x
    height = height or scene.render.resolution_y
    if maintain_aspect_ratio:
        ratio = scene.render.resolution_x / scene.render.resolution_y
        height = round(width / ratio)

    # Get frame range.
    if start_frame is None:
        start_frame = scene.frame_start
    if end_frame is None:
        end_frame = scene.frame_end
    if step_frame is None:
        step_frame = 1
    frame_range = (start_frame, end_frame, step_frame)

    if filepath is None:
        filepath = scene.render.filepath

    filepath = Path(filepath)
    if filepath.suffix:
        filepath = filepath.parent.joinpath(filepath.stem)


    render_options = {
        "filepath": f"{filepath}.",
        "resolution_x": width,
        "resolution_y": height,
        "use_overwrite": overwrite,
    }

    image_settings = image_settings or ImageSettings.copy()

    with contextlib.ExitStack() as stack:
        stack.enter_context(maintained_time())
        stack.enter_context(maintained_selection())
        stack.enter_context(maintained_visibility())
        window = stack.enter_context(_independent_window())

        applied_view(window, camera, isolate, focus, options=display_options)

        stack.enter_context(maintain_camera(window, camera))
        stack.enter_context(applied_frame_range(window, *frame_range))
        stack.enter_context(applied_render_options(window, render_options))
        stack.enter_context(applied_image_settings(window, image_settings))

        with context_override(window=window):
            bpy.ops.render.opengl(
                animation=True,
                render_keyed_only=False,
                sequencer=False,
                write_still=False,
                view_context=True,
            )

    return str(filepath) + get_extension_from_image_settings(image_settings)


ImageSettings = {
    "file_format": "FFMPEG",
    "color_mode": "RGB",
    "ffmpeg": {
        "format": "QUICKTIME",
        "use_autosplit": False,
        "codec": "H264",
        "constant_rate_factor": "MEDIUM",
        "gopsize": 18,
        "use_max_b_frames": False,
    },
}

FILE_EXTENSIONS = {
    "JPEG": ".jpg",
    "JPEG2000": ".jpg",
    "TARGA": ".tga",
    "TARGA_RAW": ".tga",
    "OPEN_EXR": ".exr",
    "OPEN_EXR_MULTILAYER": ".exr",
    "AVI_JPEG": ".avi",
    "AVI_RAW": ".avi",
    "FFMcPEG": {
        "QUICKTIME": ".mov",
        "MPEG4": ".mp4",
        "MPEG2": ".mpg",
        "MPEG1": ".mpg",
        "FLASH": ".flv",
    },
}

def get_extension_from_image_settings(image_settings):
    """Get the extension output from the preset image settings based on
    file format and ffmpeg format.

    Args:
        image_settings (dict): The image settings

    Returns:
        str: The extension.
    """
    file_format = image_settings.get("file_format")

    if file_format == "FFMPEG":
        if image_settings.get("ffmpeg"):
            ffmpeg_format = image_settings.get("format")
            if ffmpeg_format in FILE_EXTENSIONS["FFMPEG"]:
                return FILE_EXTENSIONS["FFMPEG"][ffmpeg_format]
            if ffmpeg_format:
                return "." + ffmpeg_format.lower()

    elif file_format in FILE_EXTENSIONS:
        return FILE_EXTENSIONS[file_format]
    elif file_format:
        return "." + file_format.lower()

    return ""


def isolate_objects(window, objects, focus=None):
    """Isolate selection"""

    for obj in bpy.context.scene.objects:
        try:
            obj.hide_set(obj not in objects)
        except RuntimeError:
            continue

    deselect_all()

    focus = focus or objects
    for obj in focus:
        try:
            obj.select_set(True)
        except RuntimeError:
            continue

    with context_override(selected=focus, window=window):
        bpy.ops.view3d.view_axis(type="FRONT")
        bpy.ops.view3d.view_selected(use_all_regions=False)

    deselect_all()


def _apply_options(entity, options):
    for option, value in options.items():
        if isinstance(value, dict):
            _apply_options(getattr(entity, option), value)
        else:
            setattr(entity, option, value)


def applied_view(window, camera, isolate=None, focus=None, options=None):
    """Apply view options to window."""
    # Change area of window to 3D view
    area = window.screen.areas[0]
    area.ui_type = "VIEW_3D"
    space = area.spaces[0]

    visible = [obj for obj in window.scene.objects if obj.visible_get()]

    if camera == "AUTO":
        space.region_3d.view_perspective = "ORTHO"
        isolate_objects(window, isolate or visible, focus)
    else:
        isolate_objects(window, isolate or visible, focus)
        space.camera = window.scene.objects.get(camera)
        space.region_3d.view_perspective = "CAMERA"

    if isinstance(options, dict):
        _apply_options(space, options)
    else:
        space.shading.type = "SOLID"
        space.shading.color_type = "MATERIAL"
        space.show_gizmo = False
        space.overlay.show_overlays = False


@contextlib.contextmanager
def applied_frame_range(window, start, end, step):
    """Context manager for setting frame range."""
    # Store current frame range
    current_frame_start = window.scene.frame_start
    current_frame_end = window.scene.frame_end
    current_frame_step = window.scene.frame_step
    # Apply frame range
    window.scene.frame_start = start
    window.scene.frame_end = end
    window.scene.frame_step = step
    try:
        yield
    finally:
        # Restore frame range
        window.scene.frame_start = current_frame_start
        window.scene.frame_end = current_frame_end
        window.scene.frame_step = current_frame_step


@contextlib.contextmanager
def applied_render_options(window, options):
    """Context manager for setting render options."""
    render = window.scene.render

    # Store current settings
    original = {}
    for opt in options.copy():
        try:
            original[opt] = getattr(render, opt)
        except ValueError:
            options.pop(opt)

    # Apply settings
    _apply_options(render, options)

    try:
        yield
    finally:
        # Restore previous settings
        _apply_options(render, original)


@contextlib.contextmanager
def applied_image_settings(window, options):
    """Context manager to override image settings."""

    ffmpeg = options.pop("ffmpeg", {})
    render = window.scene.render

    # Store current image settings
    original = {}
    for opt in options.copy():
        try:
            original[opt] = getattr(render.image_settings, opt)
        except ValueError:
            options.pop(opt)

    # Store current ffmpeg settings
    original_ffmpeg = {}
    for opt in ffmpeg.copy():
        try:
            original_ffmpeg[opt] = getattr(render.ffmpeg, opt)
        except ValueError:
            ffmpeg.pop(opt)

    # Apply image settings
    for opt, value in options.items():
        setattr(render.image_settings, opt, value)

    # Apply ffmpeg settings
    for opt, value in ffmpeg.items():
        setattr(render.ffmpeg, opt, value)

    try:
        yield
    finally:
        # Restore previous settings
        for opt, value in original.items():
            setattr(render.image_settings, opt, value)
        for opt, value in original_ffmpeg.items():
            setattr(render.ffmpeg, opt, value)


@contextlib.contextmanager
def maintain_camera(window, camera):
    """Context manager to override camera."""
    current_camera = window.scene.camera
    if camera in window.scene.objects:
        window.scene.camera = window.scene.objects.get(camera)
    try:
        yield
    finally:
        window.scene.camera = current_camera


@contextlib.contextmanager
def _independent_window():
    """Create capture-window context."""
    current_windows = set(bpy.context.window_manager.windows)
    with context_override():
        bpy.ops.wm.window_new()
    window = list(set(bpy.context.window_manager.windows) - current_windows)[0]
    try:
        yield window
    finally:
        with context_override(window=window):
            bpy.ops.wm.window_close()
