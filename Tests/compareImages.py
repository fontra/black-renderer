import io
import re
import sys
from PIL import Image, ImageChops


def compareImages(path1, path2):
    """Compare two image files and return a number representing how similar they are.
    A value of 0 means that the images are identical, a value of 1 means they are maximally
    different or not comparable (for example, when their dimensions differ).
    """
    assert path1.suffix == path2.suffix
    suffix = path1.suffix.lower()
    if suffix == ".svg":
        svgEqual = compareSVG(path1, path2)
        if svgEqual:
            return 0
        else:
            return 1
    elif suffix == ".pdf":
        pdfEqual, im1, im2 = comparePDF(path1, path2)
        if pdfEqual:
            return 0
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


def compareFiles(path1, path2):
    return path1.read_bytes() != path2.read_bytes()


_svgIgnore = [
    (rb'"surface\d+"', b'"surface***"'),
    (rb'"#surface\d+"', b'"#surface***"'),
]


def compareSVG(path1, path2):
    data1 = path1.read_bytes()
    data2 = path2.read_bytes()
    return _filterData(data1, _svgIgnore) == _filterData(data2, _svgIgnore)


_pdfIgnore = [
    (rb"/Producer \(cairo [^ ]+ \(", b"/Producer (cairo ****** ("),
    (rb"/CreationDate \([^)]+\)", b"/CreationDate (00000000)"),
    (rb"0000000000 65535 f[^t]+trailer", b"******"),
    (rb"startxref[^%]+%%EOF", b"******"),
]


def comparePDF(path1, path2):
    data1 = path1.read_bytes()
    data2 = path2.read_bytes()
    if _filterData(data1, _pdfIgnore) == _filterData(data2, _pdfIgnore):
        return True, None, None
    if sys.platform == "darwin":
        im1 = macRenderPDF(data1)
        im2 = macRenderPDF(data2)
        return None, im1, im2
    else:
        return False, None, None


def _filterData(data, ignorePatterns):
    for pat, repl in ignorePatterns:
        data = re.sub(pat, repl, data)
    return data


def macRenderPDF(data):
    import AppKit

    pdf = AppKit.PDFDocument.alloc().initWithData_(data)
    if pdf.pageCount() != 1:
        return None
    page = pdf.pageAtIndex_(0)
    image = AppKit.NSImage.alloc().initWithData_(page.dataRepresentation())
    return Image.open(io.BytesIO(image.TIFFRepresentation()))
