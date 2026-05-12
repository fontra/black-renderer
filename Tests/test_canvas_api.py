import pathlib
import pytest
from fontTools.misc.transform import Identity
from fontTools.ttLib.tables.otTables import CompositeMode, ExtendMode
from blackrenderer.backends import getSurfaceClass
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


test_colorStopValues = [
    (0, 1),
]

test_extendModes = [ExtendMode.PAD, ExtendMode.REPEAT, ExtendMode.REFLECT]


@pytest.mark.parametrize("stopOffsets", test_colorStopValues)
@pytest.mark.parametrize("extend", test_extendModes)
@pytest.mark.parametrize("backendName, surfaceClass", backends)
def test_colorStops(backendName, surfaceClass, stopOffsets, extend):
    point1 = (200, 0)
    point2 = (400, 0)
    color1 = (1, 0, 0, 1)
    color2 = (0, 0, 1, 1)
    stop1, stop2 = stopOffsets
    colorLine = [(stop1, color1), (stop2, color2)]

    surface = surfaceClass()
    with surface.canvas((0, 0, 600, 100)) as canvas:
        canvas.drawRectLinearGradient(
            (0, 0, 600, 100), colorLine, point1, point2, extend, Identity
        )
        for pos in [200, 400]:
            canvas.drawRectSolid((pos, 0, 1, 100), (0, 0, 0, 1))

    ext = surface.fileExtension
    stopsString = "_".join(str(s) for s in stopOffsets)
    fileName = f"colorStops_{extend.name}_{stopsString}_{backendName}{ext}"
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)
    assertSameFileBytes(expectedPath, outputPath)


@pytest.mark.parametrize("extend", test_extendModes)
@pytest.mark.parametrize("backendName, surfaceClass", backends)
def test_sweepGradient(backendName, surfaceClass, extend):
    H, W = 400, 400
    center = (H / 2, W / 2)
    startAngle = 45
    endAngle = 315
    colors = [
        (1, 0, 0, 1),
        (0, 1, 0, 1),
        (1, 1, 0, 1),
        (1, 0.5, 1, 1),
        (0, 0, 1, 1),
    ]
    stopOffsets = [0, 0.5, 0.5, 0.6, 1]
    colorLine = list(zip(stopOffsets, colors))

    surface = surfaceClass()
    with surface.canvas((0, 0, H, W)) as canvas:
        canvas.drawRectSweepGradient(
            (0, 0, H, W), colorLine, center, startAngle, endAngle, extend, Identity
        )

    ext = surface.fileExtension
    stopsString = "_".join(str(s) for s in stopOffsets)
    fileName = f"sweepGradient_{extend.name}_{stopsString}_{backendName}{ext}"
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)
    assertSameFileBytes(expectedPath, outputPath)


def assertSameFileBytes(expectedPath, outputPath):
    if expectedPath.read_bytes() != outputPath.read_bytes():
        pytest.fail(
            f"output differs from expected golden:\n"
            f"expected: {expectedPath}\n"
            f"output:   {outputPath}",
            pytrace=False,
        )


test_compositeModes = [
    CompositeMode.CLEAR,
    CompositeMode.SRC,
    CompositeMode.DEST,
    CompositeMode.SRC_OVER,
    CompositeMode.DEST_OVER,
    CompositeMode.SRC_IN,
    CompositeMode.DEST_IN,
    CompositeMode.SRC_OUT,
    CompositeMode.DEST_OUT,
    CompositeMode.SRC_ATOP,
    CompositeMode.DEST_ATOP,
    CompositeMode.XOR,
    CompositeMode.PLUS,
    CompositeMode.SCREEN,
    CompositeMode.OVERLAY,
    CompositeMode.DARKEN,
    CompositeMode.LIGHTEN,
    CompositeMode.COLOR_DODGE,
    CompositeMode.COLOR_BURN,
    CompositeMode.HARD_LIGHT,
    CompositeMode.SOFT_LIGHT,
    CompositeMode.DIFFERENCE,
    CompositeMode.EXCLUSION,
    CompositeMode.MULTIPLY,
    CompositeMode.HSL_HUE,
    CompositeMode.HSL_SATURATION,
    CompositeMode.HSL_COLOR,
    CompositeMode.HSL_LUMINOSITY,
]


@pytest.mark.parametrize("compositeMode", test_compositeModes)
@pytest.mark.parametrize("backendName, surfaceClass", backends)
def test_compositeMode(backendName, surfaceClass, compositeMode):
    H, W = 400, 400
    surface = surfaceClass()
    with surface.canvas((0, 0, H, W)) as canvas:
        canvas.drawRectSolid((50, 50, 200, 200), (1, 0.2, 0, 1))
        with canvas.compositeMode(compositeMode):
            canvas.drawRectSolid((150, 150, 200, 200), (0, 0.2, 1, 1))
    ext = surface.fileExtension
    compositeModeName = compositeMode.name.replace("_", "")  # nicer file sorting
    fileName = f"compositeMode_{compositeModeName}_{backendName}{ext}"
    expectedPath = expectedOutputDir / fileName
    outputPath = tmpOutputDir / fileName
    surface.saveImage(outputPath)
    diff = compareImages(expectedPath, outputPath)
    assert diff < 0.00013, diff
