from contextlib import contextmanager
import os
from fontTools.pens.basePen import BasePen
from fontTools.ttLib.tables.otTables import CompositeMode, ExtendMode
import skia
from .base import Canvas, Surface
from .sweepGradient import normalizeSweepColorLineAndAngles

_compositeModeMap = {
    CompositeMode.CLEAR: skia.BlendMode.kClear,
    CompositeMode.SRC: skia.BlendMode.kSrc,
    CompositeMode.DEST: skia.BlendMode.kDst,
    CompositeMode.SRC_OVER: skia.BlendMode.kSrcOver,
    CompositeMode.DEST_OVER: skia.BlendMode.kDstOver,
    CompositeMode.SRC_IN: skia.BlendMode.kSrcIn,
    CompositeMode.DEST_IN: skia.BlendMode.kDstIn,
    CompositeMode.SRC_OUT: skia.BlendMode.kSrcOut,
    CompositeMode.DEST_OUT: skia.BlendMode.kDstOut,
    CompositeMode.SRC_ATOP: skia.BlendMode.kSrcATop,
    CompositeMode.DEST_ATOP: skia.BlendMode.kDstATop,
    CompositeMode.XOR: skia.BlendMode.kXor,
    CompositeMode.PLUS: skia.BlendMode.kPlus,
    CompositeMode.SCREEN: skia.BlendMode.kScreen,
    CompositeMode.OVERLAY: skia.BlendMode.kOverlay,
    CompositeMode.DARKEN: skia.BlendMode.kDarken,
    CompositeMode.LIGHTEN: skia.BlendMode.kLighten,
    CompositeMode.COLOR_DODGE: skia.BlendMode.kColorDodge,
    CompositeMode.COLOR_BURN: skia.BlendMode.kColorBurn,
    CompositeMode.HARD_LIGHT: skia.BlendMode.kHardLight,
    CompositeMode.SOFT_LIGHT: skia.BlendMode.kSoftLight,
    CompositeMode.DIFFERENCE: skia.BlendMode.kDifference,
    CompositeMode.EXCLUSION: skia.BlendMode.kExclusion,
    CompositeMode.MULTIPLY: skia.BlendMode.kMultiply,
    CompositeMode.HSL_HUE: skia.BlendMode.kHue,
    CompositeMode.HSL_SATURATION: skia.BlendMode.kSaturation,
    CompositeMode.HSL_COLOR: skia.BlendMode.kColor,
    CompositeMode.HSL_LUMINOSITY: skia.BlendMode.kLuminosity,
}


_extendModeMap = {
    ExtendMode.PAD: skia.TileMode.kClamp,
    ExtendMode.REPEAT: skia.TileMode.kRepeat,
    ExtendMode.REFLECT: skia.TileMode.kMirror,
}


class SkiaPath(BasePen):
    def __init__(self):
        super().__init__(None)
        self.path = skia.Path()

    def _moveTo(self, pt):
        self.path.moveTo(*pt)

    def _lineTo(self, pt):
        self.path.lineTo(*pt)

    def _curveToOne(self, pt1, pt2, pt3):
        self.path.cubicTo(*pt1, *pt2, *pt3)

    def _qCurveToOne(self, pt1, pt2):
        self.path.quadTo(*pt1, *pt2)

    def _closePath(self):
        self.path.close()


class SkiaCanvas(Canvas):
    def __init__(self, canvas):
        self.canvas = canvas

    @staticmethod
    def newPath():
        return SkiaPath()

    @contextmanager
    def savedState(self):
        self.canvas.save()
        try:
            yield
        finally:
            self.canvas.restore()

    @contextmanager
    def compositeMode(self, compositeMode):
        paint = skia.Paint(BlendMode=_compositeModeMap[compositeMode])
        self.canvas.saveLayer(paint=paint)
        try:
            yield
        finally:
            self.canvas.restore()

    def transform(self, transform):
        matrix = skia.Matrix()
        matrix.setAffine(transform)
        self.canvas.concat(matrix)

    def clipPath(self, path):
        self.canvas.clipPath(path.path, doAntiAlias=True)

    def drawPathSolid(self, path, color):
        paint = skia.Paint(
            AntiAlias=True,
            Color=skia.Color4f(tuple(color)),
            Style=skia.Paint.kFill_Style,
        )
        self._drawPath(path, paint)

    def drawPathLinearGradient(
        self, path, colorLine, pt1, pt2, extendMode, gradientTransform
    ):
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeLinear(
            points=[pt1, pt2],
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            localMatrix=matrix,
        )
        self._drawPath(path, skia.Paint(AntiAlias=True, Shader=shader))

    def drawPathRadialGradient(
        self,
        path,
        colorLine,
        startCenter,
        startRadius,
        endCenter,
        endRadius,
        extendMode,
        gradientTransform,
    ):
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeTwoPointConical(
            start=startCenter,
            startRadius=startRadius,
            end=endCenter,
            endRadius=endRadius,
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            localMatrix=matrix,
        )
        self._drawPath(path, skia.Paint(AntiAlias=True, Shader=shader))

    def drawPathSweepGradient(
        self,
        path,
        colorLine,
        center,
        startAngle,
        endAngle,
        extendMode,
        gradientTransform,
    ):
        colorLine, startAngle, endAngle = normalizeSweepColorLineAndAngles(
            colorLine, startAngle, endAngle
        )
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeSweep(
            cx=center[0],
            cy=center[1],
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            startAngle=startAngle,
            endAngle=endAngle,
            localMatrix=matrix,
        )
        self._drawPath(path, skia.Paint(AntiAlias=True, Shader=shader))

    def _drawPath(self, path, paint):
        if path is None:
            # unbounded source, paint the entire clip area
            self.canvas.drawPaint(paint)
        else:
            self.canvas.drawPath(path.path, paint)


def _unpackColorLine(colorLine):
    colors = []
    stops = []
    for stop, color in colorLine:
        colors.append(int(skia.Color4f(tuple(color))))
        stops.append(stop)
    return colors, stops


class _SkiaBaseSurface(Surface):
    @contextmanager
    def canvas(self, boundingBox):
        x, y, xMax, yMax = boundingBox
        width = xMax - x
        height = yMax - y
        skCanvas, surfaceData = self._setupSkCanvas(x, y, width, height)
        skCanvas.translate(-x, height + y)
        skCanvas.scale(1, -1)
        yield SkiaCanvas(skCanvas)
        self._finalizeCanvas(surfaceData)


class SkiaPixelSurface(_SkiaBaseSurface):
    fileExtension = ".png"

    def __init__(self):
        self._image = None

    def _setupSkCanvas(self, x, y, width, height):
        surface = skia.Surface(width, height)
        return surface.getCanvas(), surface

    def _finalizeCanvas(self, surface):
        self._image = surface.makeImageSnapshot()

    def saveImage(self, path, format=skia.kPNG):
        self._image.save(os.fspath(path), format)


class SkiaPDFSurface(_SkiaBaseSurface):
    fileExtension = ".pdf"

    def __init__(self):
        self._pictures = []

    def _setupSkCanvas(self, x, y, width, height):
        recorder = skia.PictureRecorder()
        return recorder.beginRecording(width, height), recorder

    def _finalizeCanvas(self, recorder):
        self._pictures.append(recorder.finishRecordingAsPicture())

    def saveImage(self, path):
        stream = skia.FILEWStream(os.fspath(path))
        with skia.PDF.MakeDocument(stream) as document:
            for picture in self._pictures:
                x, y, width, height = picture.cullRect()
                assert x == 0 and y == 0
                with document.page(width, height) as canvas:
                    canvas.drawPicture(picture)
        stream.flush()


class SkiaSVGSurface(SkiaPDFSurface):
    fileExtension = ".svg"

    def saveImage(self, path):
        stream = skia.FILEWStream(os.fspath(path))
        picture = self._pictures[-1]
        canvas = skia.SVGCanvas.Make(picture.cullRect(), stream)
        canvas.drawPicture(picture)
        del canvas  # hand holding skia-python with GC: it needs to go before stream
        stream.flush()
