"""Disposable Image machines: acquisition, decoding, and display preparation."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageGrab, ImageOps, UnidentifiedImageError

from . import machine, mobile_stacks


FORMATS = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif"}
INPUT_ERRORS = (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError)


def read_source(source):
    """Acquire pixels or file bytes without accessing Tk."""
    if source["kind"] == "file":
        return Path(source["path"]).read_bytes()
    if source["kind"] != "clipboard":
        raise ValueError("Unknown image source")
    contents = ImageGrab.grabclipboard()
    if isinstance(contents, Image.Image):
        with BytesIO() as destination:
            contents.save(destination, format="PNG")
            return destination.getvalue()
    if isinstance(contents, list) and len(contents) == 1:
        return Path(contents[0]).read_bytes()
    raise ValueError("The clipboard must contain an image or one image file")


def inspect_image(data):
    with Image.open(BytesIO(data)) as decoded:
        if decoded.format not in FORMATS:
            raise ValueError("Choose a JPEG, PNG, or GIF image")
        decoded.seek(0)
        decoded.load()
        return FORMATS[decoded.format]


def finish_image_error(error):
    mobile_stacks.stack()["registers"].pop("image-bytes", None)
    mobile_stacks.set_register(("image-result", {"status": "error", "error": str(error)}))
    machine.request_machine_retirement()


def continue_through_disk(entry, continuation):
    machine.continue_with_frames([
        {"machine": machine.get_current_runtime()["name"], "entry": continuation},
        {"machine": "DISK", "entry": entry},
    ])


def handle_when_image_receives_import_image():
    try:
        data = read_source(mobile_stacks.get_register("source"))
        if machine.a_thread_died_unexpectedly.is_set():
            return
        extension = inspect_image(data)
    except INPUT_ERRORS as error:
        finish_image_error(error)
        return
    if machine.a_thread_died_unexpectedly.is_set():
        return
    mobile_stacks.set_register(("image-bytes", data))
    mobile_stacks.set_register(("image-extension", extension))
    continue_through_disk("WRITE_IMAGE_ASSET", "IMAGE_ASSET_WRITTEN")


def handle_when_image_asset_has_been_written():
    error = mobile_stacks.get_register("image-error")
    if error:
        finish_image_error(error)
        return
    mobile_stacks.stack()["registers"].pop("image-bytes", None)
    mobile_stacks.set_register(("image-result", {
        "status": "ok", "image-asset": mobile_stacks.get_register("image-asset"),
    }))
    machine.request_machine_retirement()


def handle_when_image_receives_load_preview():
    continue_through_disk("READ_IMAGE_ASSET", "PREVIEW_ASSET_READ")


def handle_when_image_preview_asset_has_been_read():
    error = mobile_stacks.get_register("image-error")
    if error:
        finish_image_error(error)
        return
    width = mobile_stacks.get_register("width")
    height = mobile_stacks.get_register("height")
    data = mobile_stacks.stack()["registers"].pop("image-bytes")
    try:
        with Image.open(BytesIO(data)) as decoded:
            if decoded.format not in FORMATS:
                raise ValueError("Unsupported stored image format")
            decoded.seek(0)
            decoded.load()
            if machine.a_thread_died_unexpectedly.is_set():
                return
            prepared = ImageOps.exif_transpose(decoded).convert("RGBA")
            prepared.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
            pixels = prepared.tobytes()
    except INPUT_ERRORS as error:
        finish_image_error(error)
        return
    if machine.a_thread_died_unexpectedly.is_set():
        return
    mobile_stacks.set_register(("image-result", {
        "status": "ok", "image-asset": mobile_stacks.get_register("image-asset"),
        "width": prepared.width, "height": prepared.height, "pixels": pixels,
        "request-width": width, "request-height": height,
    }))
    machine.request_machine_retirement()


HANDLERS = {
    "IMPORT_IMAGE": handle_when_image_receives_import_image,
    "IMAGE_ASSET_WRITTEN": handle_when_image_asset_has_been_written,
    "LOAD_PREVIEW": handle_when_image_receives_load_preview,
    "PREVIEW_ASSET_READ": handle_when_image_preview_asset_has_been_read,
}
