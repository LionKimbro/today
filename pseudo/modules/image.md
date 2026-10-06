# `image.py`

OWNS: acquisition, validation, decoding, and preview preparation for images.
Each router-created IMAGE instance keeps its address while its Mobile Stack
visits Disk; it requests retirement only after the final result is ready.

IMPORT_IMAGE reads an external file or the clipboard on its own worker thread.
JPEG, PNG, and GIF files are preserved byte-for-byte. Clipboard pixels become
PNG. It decodes the first frame to validate the input before asking Disk to
WRITE_IMAGE_ASSET. IMAGE_ASSET_WRITTEN returns an `image-result` containing
`status: ok` and the day-relative `image-asset`, then requests retirement.

LOAD_PREVIEW asks Disk to READ_IMAGE_ASSET. PREVIEW_ASSET_READ decodes the first
frame, applies EXIF orientation, converts to RGBA, and fits within the requested
width and height without enlarging. Its result carries actual `width`, `height`,
RGBA `pixels`, and original bounds `request-width`, `request-height`.

Expected clipboard, file, format, and decode errors return `status: error` with
an `error` string. Unexpected faults use the shared fatal worker boundary.
Handlers check the fatal event between acquisition, decode, and handoff stages.

DOES NOT OWN: Tk resources, canonical panel references, or stored asset writes.
There is no shared mutable image working register: each instance uses the
traveling registers of its own currently held Mobile Stack.
