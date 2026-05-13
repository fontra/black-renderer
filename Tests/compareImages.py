import io
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageChops


def compareImages(path1, path2):
    """Compare two image files and return a number representing how similar they are.
    A value of 0 means that the images are identical, a value of 1 means they are
    maximally different or not comparable (for example, when their dimensions differ).
    """
    assert path1.suffix == path2.suffix
    suffix = path1.suffix.lower()
    if suffix == ".svg":
        im1 = renderSVG(path1)
        im2 = renderSVG(path2)
        if im1 is None or im2 is None:
            return 1
    elif suffix == ".pdf":
        im1 = renderPDF(path1, path2.parent)
        im2 = renderPDF(path2, path2.parent)
        if im1 is None or im2 is None:
            return 1
    else:
        im1 = _normalizeTransparentPixels(Image.open(path1))
        im2 = _normalizeTransparentPixels(Image.open(path2))

    if im1.size != im2.size:
        # Dimensions differ, can't compare further
        return 1

    if im1 == im2:
        # Image data is identical (I checked PIL's Image.__eq__ method: it's solid)
        return 0

    # Get the difference between the images
    diff = ImageChops.difference(im1, im2)

    # We'll calculate the average difference based on the histogram provided by PIL
    hist = diff.histogram()
    assert (
        len(hist) == 4 * 256
    )  # Assuming 4x8-bit RGBA for now. TODO: make this work for L and RGB modes
    # Sum the histograms of each channel
    summedHist = [
        sum(hist[pixelValue + ch * 256] for ch in range(4)) for pixelValue in range(256)
    ]

    assert len(summedHist) == 256
    assert sum(hist) == sum(summedHist)
    # Calculate the average of the difference
    # First add all pixel values together
    totalSum = sum(summedHist[pixelValue] * pixelValue for pixelValue in range(256))
    # Then divide by the total number of channel values
    average = totalSum / sum(summedHist)
    # Scale pixel value range from 0-255 to 0-1
    average = average / 255
    assert 0.0 <= average <= 1.0
    return average


def _normalizeTransparentPixels(image):
    """Make fully transparent pixels comparable regardless of hidden RGB data."""
    image = image.convert("RGBA")
    if image.getchannel("A").getextrema()[0] != 0:
        return image

    transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
    alpha = image.getchannel("A")
    return Image.composite(image, transparent, alpha)


def renderSVG(path):
    if shutil.which("rsvg-convert") is None:
        return None

    with tempfile.TemporaryDirectory(dir=path.parent) as tempDir:
        outputPath = f"{tempDir}/rendered.png"
        command = ["rsvg-convert", "--format=png", "--output", outputPath]
        renderSize = _getSVGRenderSize(path)
        if renderSize is not None:
            width, height = renderSize
            command.extend(["--width", str(width), "--height", str(height)])
        command.append(str(path))
        subprocess.run(
            command,
            check=True,
        )
        return _normalizeTransparentPixels(Image.open(outputPath))


def _getSVGRenderSize(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    viewBox = root.attrib.get("viewBox")
    if viewBox is not None:
        values = [float(value) for value in viewBox.split()]
        if len(values) == 4:
            return _roundDimension(values[2]), _roundDimension(values[3])

    width = _parseSVGDimension(root.attrib.get("width"))
    height = _parseSVGDimension(root.attrib.get("height"))
    if width is not None and height is not None:
        return _roundDimension(width), _roundDimension(height)
    return None


def _parseSVGDimension(value):
    if value is None:
        return None
    for suffix in ("px", "pt"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    try:
        return float(value)
    except ValueError:
        return None


def _roundDimension(value):
    return max(1, round(value))


def renderPDF(path, tempParent):
    if sys.platform == "darwin":
        image = macRenderPDF(path.read_bytes())
        if image is None:
            return None
        return _normalizeTransparentPixels(image)

    if shutil.which("pdftocairo") is None:
        return None

    with tempfile.TemporaryDirectory(dir=tempParent) as tempDir:
        outputPrefix = f"{tempDir}/rendered"
        subprocess.run(
            ["pdftocairo", "-singlefile", "-png", "-r", "72", str(path), outputPrefix],
            check=True,
        )
        return _normalizeTransparentPixels(Image.open(f"{outputPrefix}.png"))


def macRenderPDF(data):
    import AppKit
    import Quartz

    pdf = Quartz.PDFDocument.alloc().initWithData_(data)
    if pdf.pageCount() != 1:
        return None
    page = pdf.pageAtIndex_(0)
    image = AppKit.NSImage.alloc().initWithData_(page.dataRepresentation())
    return Image.open(io.BytesIO(image.TIFFRepresentation()))
