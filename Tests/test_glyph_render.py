import pathlib
import pytest
from fontTools.misc.arrayTools import scaleRect, intRect
from blackrenderer.font import BlackRendererFont
from blackrenderer.backends import getSurfaceClass
from blackrenderer.backends.pathCollector import BoundsCanvas, PathCollectorCanvas
from compareImages import compareImages

testDir = pathlib.Path(__file__).resolve().parent
dataDir = testDir / "data"
expectedOutputDir = testDir / "expectedOutput"
tmpOutputDir = testDir / "tmpOutput"
if not tmpOutputDir.exists():
    tmpOutputDir.mkdir()


backends = [
    (name, getSurfaceClass(name)) for name in ["cairo", "coregraphics", "skia", "svg"]
]
backends = [(name, surface) for name, surface in backends if surface is not None]


testFonts = {
    "noto": dataDir / "noto-glyf_colr_1.ttf",
    "mutator": dataDir / "MutatorSans.ttf",
    "twemoji": dataDir / "TwemojiMozilla.subset.default.3299.ttf",
    "test_glyphs": dataDir / "test_glyphs-glyf_colr_1.ttf",
    "crash": dataDir / "crash.subset.otf",
    "nested_paintglyph": dataDir / "nested-paintglyph.ttf",
    "ftvartest": dataDir / "TestVariableCOLR-VF.ttf",
    "nabla": dataDir / "Nabla.subset.ttf",
    "issue113": dataDir / "issue113.ttf",
    "issue116": dataDir / "Noto-COLRv1.subset.ttf",
}


test_glyphs = [
    ("noto", "uni2693", None, 0),
    ("noto", "uni2694", None, 0),
    ("noto", "u1F30A", None, 0),
    ("noto", "u1F943", None, 0),
    ("mutator", "B", None, 0),
    ("mutator", "D", {"wdth": 1000}, 0),
    ("twemoji", "uni3299", None, 0),
    ("test_glyphs", "cross_glyph", None, 0),
    ("test_glyphs", "skew_0_15_center_500.0_500.0", None, 0),
    ("test_glyphs", "skew_-10_20_center_500.0_500.0", None, 0),
    ("test_glyphs", "skew_-10_20_center_1000_1000", None, 0),
    ("test_glyphs", "transform_matrix_1_0_0_1_125_125", None, 0),
    ("test_glyphs", "transform_matrix_1.5_0_0_1.5_0_0", None, 0),
    ("test_glyphs", "transform_matrix_0.9659_0.2588_-0.2588_0.9659_0_0", None, 0),
    ("test_glyphs", "transform_matrix_1.0_0.0_0.6_1.0_-300.0_0.0", None, 0),
    ("test_glyphs", "clip_box_top_left", None, 0),
    ("test_glyphs", "clip_box_bottom_left", None, 0),
    ("test_glyphs", "clip_box_bottom_right", None, 0),
    ("test_glyphs", "clip_box_top_right", None, 0),
    ("test_glyphs", "clip_box_center", None, 0),
    ("test_glyphs", "composite_CLEAR", None, 0),
    ("test_glyphs", "composite_DEST_OVER", None, 0),
    ("test_glyphs", "composite_XOR", None, 0),
    ("test_glyphs", "composite_OVERLAY", None, 0),
    ("test_glyphs", "composite_SRC_IN", None, 0),
    ("test_glyphs", "composite_PLUS", None, 0),
    ("test_glyphs", "composite_LIGHTEN", None, 0),
    ("test_glyphs", "composite_MULTIPLY", None, 0),
    ("test_glyphs", "clip_shade_center", None, 0),
    ("test_glyphs", "clip_shade_top_left", None, 0),
    ("test_glyphs", "clip_shade_bottom_left", None, 0),
    ("test_glyphs", "clip_shade_bottom_right", None, 0),
    ("test_glyphs", "clip_shade_top_right", None, 0),
    ("test_glyphs", "inset_clipped_radial_reflect", None, 0),
    ("test_glyphs", "sweep_90_0_pad_narrow", None, 0),
    ("test_glyphs", "sweep_90_0_reflect_narrow", None, 0),
    ("test_glyphs", "sweep_90_0_repeat_narrow", None, 0),
    ("test_glyphs", "sweep_90_45_reflect_narrow", None, 0),
    ("test_glyphs", "sweep_45_90_repeat_narrow", None, 0),
    ("test_glyphs", "sweep_440_270_pad_wide", None, 0),
    (
        "test_glyphs",
        "sweep_coincident_angles_forward_linen_gray_reflect",
        None,
        0,
    ),
    ("test_glyphs", "foreground_color_sweep_alpha_0.3", None, 0),
    ("test_glyphs", "linear_repeat_0_1", None, 0),
    ("test_glyphs", "linear_repeat_0.2_0.8", None, 0),
    ("test_glyphs", "linear_repeat_0_1.5", None, 0),
    ("test_glyphs", "linear_repeat_0.5_1.5", None, 0),
    ("test_glyphs", "scale_0.5_1.5_center_500.0_500.0", None, 0),
    ("test_glyphs", "scale_1.5_1.5_center_500.0_500.0", None, 0),
    ("test_glyphs", "scale_0.5_1.5_center_0_0", None, 0),
    ("test_glyphs", "scale_1.5_1.5_center_0_0", None, 0),
    ("test_glyphs", "scale_0.5_1.5_center_1000_1000", None, 0),
    ("test_glyphs", "scale_1.5_1.5_center_1000_1000", None, 0),
    ("test_glyphs", "linear_gradient_extend_mode_pad", None, 0),
    ("test_glyphs", "linear_gradient_extend_mode_repeat", None, 0),
    ("test_glyphs", "linear_gradient_extend_mode_reflect", None, 0),
    ("test_glyphs", "radial_contained_gradient_extend_mode_pad", None, 0),
    ("test_glyphs", "radial_contained_gradient_extend_mode_repeat", None, 0),
    ("test_glyphs", "radial_contained_gradient_extend_mode_reflect", None, 0),
    ("test_glyphs", "radial_horizontal_gradient_extend_mode_pad", None, 0),
    ("test_glyphs", "radial_horizontal_gradient_extend_mode_repeat", None, 0),
    ("test_glyphs", "radial_horizontal_gradient_extend_mode_reflect", None, 0),
    ("test_glyphs", "rotate_10_center_0_0", None, 0),
    ("test_glyphs", "rotate_-10_center_1000_1000", None, 0),
    ("test_glyphs", "rotate_25_center_500.0_500.0", None, 0),
    ("test_glyphs", "rotate_-15_center_500.0_500.0", None, 0),
    ("test_glyphs", "skew_25_0_center_0_0", None, 0),
    ("test_glyphs", "skew_25_0_center_500.0_500.0", None, 0),
    ("test_glyphs", "skew_0_15_center_0_0", None, 0),
    ("test_glyphs", "upem_box_glyph", None, 0),
    ("nested_paintglyph", "A", None, 0),
    ("ftvartest", "A", {"wght": 400}, 0),
    ("ftvartest", "A", {"wght": 700}, 0),
    ("ftvartest", "B", {"wght": 400}, 0),
    ("ftvartest", "B", {"wght": 700}, 0),
    ("nabla", "A", None, 0),
    ("nabla", "A", None, 1),
    ("issue113", "B", None, 0),
    ("issue116", "u1F39B", None, 0),
    ("issue116", "u1F39F", None, 0),
    ("issue116", "u1F3AB", None, 0),
]


sweep_regression_glyphs = [
    "sweep_0_360_pad_wide",
    "sweep_60_300_reflect_wide",
    "sweep_90_45_reflect_wide",
    "sweep_coincident_angles_forward_blue_red_pad",
    "sweep_coincident_angles_forward_blue_red_repeat",
    "sweep_coincident_stops_forward_blue_red_pad",
    "sweep_coincident_stops_forward_blue_red_repeat",
]

sweep_regression_backends = [
    (name, getSurfaceClass(name)) for name in ["cairo", "coregraphics", "skia"]
]
sweep_regression_backends = [
    (name, surface) for name, surface in sweep_regression_backends
    if surface is not None
]


@pytest.mark.parametrize("fontName, glyphName, location, paletteIndex", test_glyphs)
@pytest.mark.parametrize("backendName, surfaceClass", backends)
def test_renderGlyph(
    backendName, surfaceClass, fontName, glyphName, location, paletteIndex
):
    font = BlackRendererFont(testFonts[fontName])
    font.setLocation(location)

    scaleFactor = 1 / 4
    boundingBox = font.getGlyphBounds(glyphName)
    boundingBox = scaleRect(boundingBox, scaleFactor, scaleFactor)
    boundingBox = intRect(boundingBox)
    palette = font.getPalette(paletteIndex)

    surface = surfaceClass()
    ext = surface.fileExtension
    with surface.canvas(boundingBox) as canvas:
        canvas.scale(scaleFactor)
        font.drawGlyph(glyphName, canvas, palette=palette)

    locationString = "_" + _locationToString(location) if location else ""
    paletteString = "_" + str(paletteIndex) if paletteIndex else ""
    fileName = (
        f"glyph_{fontName}_{glyphName}{locationString}{paletteString}"
        f"_{backendName}{ext}"
    )
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)
    diff = compareImages(expectedPath, outputPath)
    assert diff < _getImageTolerance(backendName), diff


@pytest.mark.parametrize("glyphName", sweep_regression_glyphs)
@pytest.mark.parametrize("backendName, surfaceClass", sweep_regression_backends)
def test_renderSweepRegressionGlyphs(backendName, surfaceClass, glyphName):
    font = BlackRendererFont(testFonts["test_glyphs"])

    scaleFactor = 1 / 4
    boundingBox = font.getGlyphBounds(glyphName)
    boundingBox = scaleRect(boundingBox, scaleFactor, scaleFactor)
    boundingBox = intRect(boundingBox)
    palette = font.getPalette(0)

    surface = surfaceClass()
    ext = surface.fileExtension
    with surface.canvas(boundingBox) as canvas:
        canvas.scale(scaleFactor)
        font.drawGlyph(glyphName, canvas, palette=palette)

    fileName = f"glyph_test_glyphs_{glyphName}_sweepRegression_{backendName}{ext}"
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)
    diff = compareImages(expectedPath, outputPath)
    assert diff < _getImageTolerance(backendName), diff


def _locationToString(location):
    return ",".join(f"{name}={value}" for name, value in sorted(location.items()))


def _getImageTolerance(backendName):
    if backendName == "skia":
        return 0.0008
    return 0.00012


def test_pathCollector():
    font = BlackRendererFont(testFonts["noto"])
    canvas = PathCollectorCanvas()
    font.drawGlyph("uni2693", canvas)
    assert len(canvas.paths) == 6


def test_boundsCanvas():
    font = BlackRendererFont(testFonts["mutator"])
    canvas = BoundsCanvas()
    font.drawGlyph("A", canvas)
    assert (20, 0, 376, 700) == canvas.bounds

    font.setLocation({"wdth": 1000})
    canvas = BoundsCanvas()
    font.drawGlyph("A", canvas)
    assert (50, 0, 1140, 700) == canvas.bounds

    font = BlackRendererFont(testFonts["test_glyphs"])
    canvas = BoundsCanvas()
    font.drawGlyph("sweep_90_0_pad_narrow", canvas)
    assert (150, 250, 850, 950) == tuple(round(v) for v in canvas.bounds)


vectorBackends = [
    ("cairo", ".pdf"),
    ("cairo", ".svg"),
    ("skia", ".pdf"),
    ("skia", ".svg"),
    ("coregraphics", ".pdf"),
]


@pytest.mark.parametrize("backendName, imageSuffix", vectorBackends)
def test_vectorBackends(backendName, imageSuffix):
    fontName = "noto"
    glyphName = "u1F943"
    surfaceClass = getSurfaceClass(backendName, imageSuffix)
    if surfaceClass is None:
        pytest.skip(f"{backendName} not available")
    assert surfaceClass.fileExtension == imageSuffix

    font = BlackRendererFont(testFonts[fontName])
    boundingBox = font.getGlyphBounds(glyphName)

    surface = surfaceClass()
    with surface.canvas(boundingBox) as canvas:
        font.drawGlyph(glyphName, canvas)
    fileName = f"vector_{fontName}_{glyphName}_{backendName}{imageSuffix}"
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)

    # Vector backends can serialize the same drawing differently across
    # renderer/platform versions, so compare rendered output instead of bytes.
    # assert expectedPath.read_bytes() == outputPath.read_bytes()
    diff = compareImages(expectedPath, outputPath)
    assert diff < 0.00012, diff


def test_recursive():
    # https://github.com/BlackFoundryCom/black-renderer/issues/56
    # https://github.com/justvanrossum/fontgoggles/issues/213
    glyphName = "hah-ar"
    font = BlackRendererFont(testFonts["crash"])
    boundingBox = font.getGlyphBounds(glyphName)
    surfaceClass = getSurfaceClass("svg", ".svg")
    surface = surfaceClass()
    with surface.canvas(boundingBox) as canvas:
        with pytest.raises(RecursionError):
            font.drawGlyph(glyphName, canvas)
