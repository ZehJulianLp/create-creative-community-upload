import gzip
import io
import warnings
import zlib
from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

IMAGE_LIMIT = 8 * 1024 * 1024
SCHEMATIC_LIMIT = 20 * 1024 * 1024
NBT_LIMIT = 64 * 1024 * 1024


def read_image(upload):
    data = upload.read(IMAGE_LIMIT + 1)
    if len(data) > IMAGE_LIMIT:
        raise ValueError("Das Bild darf höchstens 8 MB groß sein.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as picture:
                if picture.format not in ("PNG", "JPEG", "WEBP"):
                    raise ValueError("Bitte lade ein PNG-, JPEG- oder WebP-Bild hoch.")
                if picture.width * picture.height > 20_000_000:
                    raise ValueError("Das Bild darf höchstens 20 Megapixel haben.")
                picture.verify()
            with Image.open(io.BytesIO(data)) as picture:
                picture = ImageOps.exif_transpose(picture).convert("RGB")
                picture.thumbnail((2560, 2560))
                output = io.BytesIO()
                picture.save(output, format="WEBP", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise ValueError("Das Bild ist beschädigt oder wird nicht unterstützt.") from error
    return uuid4().hex + ".webp", output.getvalue()


def read_schematic(upload):
    if Path(upload.filename).suffix.lower() != ".nbt":
        raise ValueError("Bitte lade eine Create-Schematic als .nbt-Datei hoch.")
    data = upload.read(SCHEMATIC_LIMIT + 1)
    if len(data) > SCHEMATIC_LIMIT:
        raise ValueError("Die Schematic darf höchstens 20 MB groß sein.")
    try:
        if data.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                document = compressed.read(NBT_LIMIT + 1)
        else:
            document = data
    except (OSError, EOFError, zlib.error) as error:
        raise ValueError("Die komprimierte Schematic ist beschädigt.") from error
    if len(document) > NBT_LIMIT:
        raise ValueError("Die entpackte Schematic darf höchstens 64 MB groß sein.")
    # NBT-Compound-Header prüfen; Spielkompatibilität wird nicht simuliert.
    if len(document) < 4 or document[0] != 10 or document[-1] != 0:
        raise ValueError("Die Datei besitzt keinen gültigen NBT-Compound-Header.")
    name_length = int.from_bytes(document[1:3], "big")
    if name_length > len(document) - 4:
        raise ValueError("Der NBT-Dateikopf ist unvollständig.")
    original = secure_filename(upload.filename)[:150] or "schematic.nbt"
    if not original.lower().endswith(".nbt"):
        original += ".nbt"
    return uuid4().hex + ".nbt", data, original


def write_uploads(files):
    written = []
    try:
        for name, data in files:
            path = Path(current_app.config["UPLOAD_FOLDER"]) / name
            with path.open("xb") as destination:
                written.append(name)
                destination.write(data)
    except OSError:
        remove_uploads(written)
        raise


def remove_uploads(names):
    for name in names:
        try:
            (Path(current_app.config["UPLOAD_FOLDER"]) / name).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("Upload-Datei konnte nicht entfernt werden: %s", name)
