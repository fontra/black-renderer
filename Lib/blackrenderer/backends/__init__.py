from collections import defaultdict
import importlib

_surfaces = {
    None: {
        "cairo": "blackrenderer.backends.cairo.CairoPixelSurface",
        "coregraphics": "blackrenderer.backends.coregraphics.CoreGraphicsPixelSurface",
        "skia": "blackrenderer.backends.skia.SkiaPixelSurface",
        "svg": "blackrenderer.backends.svg.SVGSurface",
    },
    ".png": {
        "cairo": "blackrenderer.backends.cairo.CairoPixelSurface",
        "coregraphics": "blackrenderer.backends.coregraphics.CoreGraphicsPixelSurface",
        "skia": "blackrenderer.backends.skia.SkiaPixelSurface",
    },
    ".pdf": {
        "cairo": "blackrenderer.backends.cairo.CairoPDFSurface",
        "coregraphics": "blackrenderer.backends.coregraphics.CoreGraphicsPDFSurface",
        "skia": "blackrenderer.backends.skia.SkiaPDFSurface",
    },
    ".svg": {
        "cairo": "blackrenderer.backends.cairo.CairoSVGSurface",
        "skia": "blackrenderer.backends.skia.SkiaSVGSurface",
        "svg": "blackrenderer.backends.svg.SVGSurface",
    },
}


def getSurfaceClass(backendName, imageExtension=None):
    fqName = _surfaces[imageExtension][backendName]
    moduleName, className = fqName.rsplit(".", 1)
    try:
        module = importlib.import_module(moduleName)
    except ModuleNotFoundError:
        return None
    return getattr(module, className)


def listBackends():
    backends = defaultdict(list)
    for suffix in _surfaces:
        if suffix is None:
            continue
        for backendName in _surfaces[suffix]:
            backends[backendName].append(suffix)
    return [
        (backendName, sorted(suffixes)) for backendName, suffixes in backends.items()
    ]
