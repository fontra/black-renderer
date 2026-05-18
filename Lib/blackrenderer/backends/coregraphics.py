from contextlib import contextmanager
from math import ceil, sqrt
import os
from fontTools.pens.basePen import BasePen
from fontTools.ttLib.tables.otTables import CompositeMode, ExtendMode
from CoreFoundation import CFDataCreateMutable
import Quartz as CG
from .base import Canvas, Surface
from .sweepGradient import buildSweepGradientPatches

_compositeModeMap = {
    CompositeMode.CLEAR: CG.kCGBlendModeClear,
    CompositeMode.SRC: CG.kCGBlendModeCopy,
    # This is wrong, but is worked around in canvas.compositeMode().
    CompositeMode.DEST: CG.kCGBlendModeNormal,
    CompositeMode.SRC_OVER: CG.kCGBlendModeNormal,
    CompositeMode.DEST_OVER: CG.kCGBlendModeDestinationOver,
    CompositeMode.SRC_IN: CG.kCGBlendModeSourceIn,
    CompositeMode.DEST_IN: CG.kCGBlendModeDestinationIn,
    CompositeMode.SRC_OUT: CG.kCGBlendModeSourceOut,
    CompositeMode.DEST_OUT: CG.kCGBlendModeDestinationOut,
    CompositeMode.SRC_ATOP: CG.kCGBlendModeSourceAtop,
    CompositeMode.DEST_ATOP: CG.kCGBlendModeDestinationAtop,
    CompositeMode.XOR: CG.kCGBlendModeXOR,
    CompositeMode.PLUS: CG.kCGBlendModePlusLighter,
    CompositeMode.SCREEN: CG.kCGBlendModeScreen,
    CompositeMode.OVERLAY: CG.kCGBlendModeOverlay,
    CompositeMode.DARKEN: CG.kCGBlendModeDarken,
    CompositeMode.LIGHTEN: CG.kCGBlendModeLighten,
    CompositeMode.COLOR_DODGE: CG.kCGBlendModeColorDodge,
    CompositeMode.COLOR_BURN: CG.kCGBlendModeColorBurn,
    CompositeMode.HARD_LIGHT: CG.kCGBlendModeHardLight,
    CompositeMode.SOFT_LIGHT: CG.kCGBlendModeSoftLight,
    CompositeMode.DIFFERENCE: CG.kCGBlendModeDifference,
    CompositeMode.EXCLUSION: CG.kCGBlendModeExclusion,
    CompositeMode.MULTIPLY: CG.kCGBlendModeMultiply,
    CompositeMode.HSL_HUE: CG.kCGBlendModeHue,
    CompositeMode.HSL_SATURATION: CG.kCGBlendModeSaturation,
    CompositeMode.HSL_COLOR: CG.kCGBlendModeColor,
    CompositeMode.HSL_LUMINOSITY: CG.kCGBlendModeLuminosity,
}


_sRGBColorSpace = CG.CGColorSpaceCreateWithName(CG.kCGColorSpaceSRGB)


class CoreGraphicsPathPen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.path = CG.CGPathCreateMutable()

    def _moveTo(self, pt):
        CG.CGPathMoveToPoint(self.path, None, *pt)

    def _lineTo(self, pt):
        CG.CGPathAddLineToPoint(self.path, None, *pt)

    def _curveToOne(self, pt1, pt2, pt3):
        CG.CGPathAddCurveToPoint(self.path, None, *pt1, *pt2, *pt3)

    def _qCurveToOne(self, pt1, pt2):
        CG.CGPathAddQuadCurveToPoint(self.path, None, *pt1, *pt2)

    def _closePath(self):
        CG.CGPathCloseSubpath(self.path)


class CoreGraphicsCanvas(Canvas):
    def __init__(self, context):
        self.context = context
        self.clipIsEmpty = None

    @staticmethod
    def newPath():
        return CoreGraphicsPathPen()

    @contextmanager
    def savedState(self):
        clipIsEmpty = self.clipIsEmpty
        CG.CGContextSaveGState(self.context)
        try:
            yield
        finally:
            CG.CGContextRestoreGState(self.context)
            self.clipIsEmpty = clipIsEmpty

    @contextmanager
    def compositeMode(self, compositeMode):
        CG.CGContextSaveGState(self.context)
        if compositeMode == CompositeMode.DEST:
            # Workaround for CG not having a blend mode corresponding
            # with CompositeMode.DEST. Setting alpha to 0 should be
            # equivalent.
            CG.CGContextSetAlpha(self.context, 0.0)
        else:
            CG.CGContextSetBlendMode(self.context, _compositeModeMap[compositeMode])
        CG.CGContextBeginTransparencyLayer(self.context, None)
        try:
            yield
        finally:
            CG.CGContextEndTransparencyLayer(self.context)
            CG.CGContextRestoreGState(self.context)

    def transform(self, transform):
        CG.CGContextConcatCTM(self.context, transform)

    def clipPath(self, path):
        if CG.CGPathGetBoundingBox(path.path) == CG.CGRectNull:
            # The path is empty, which causes *no* clip path to be set,
            # which in turn would cause the entire canvas to be filled,
            # so let's prevent that with a flag.
            self.clipIsEmpty = True
        else:
            self.clipIsEmpty = False
            CG.CGContextAddPath(self.context, path.path)
            CG.CGContextClip(self.context)

    def drawPathSolid(self, path, color):
        if self._shouldNotDrawPath(path):
            return
        if path is not None:
            CG.CGContextAddPath(self.context, path.path)
        else:
            # unbounded source, paint the existing clip area
            clipRect = CG.CGContextGetClipBoundingBox(self.context)
            CG.CGContextAddRect(self.context, clipRect)
        CG.CGContextSetFillColorWithColor(
            self.context, CG.CGColorCreate(_sRGBColorSpace, color)
        )
        CG.CGContextFillPath(self.context)

    def drawPathLinearGradient(
        self, path, colorLine, pt1, pt2, extendMode, gradientTransform
    ):
        if self._shouldNotDrawPath(path):
            return
        with self.savedState():
            if path is not None:
                CG.CGContextAddPath(self.context, path.path)
                CG.CGContextClip(self.context)
            # else: unbounded source, paint the existing clip area
            self.transform(gradientTransform)
            if extendMode in (ExtendMode.REPEAT, ExtendMode.REFLECT):
                colorLine, pt1, pt2 = _expandLinearGradient(
                    self.context, colorLine, pt1, pt2, extendMode
                )
            colors, stops = _unpackColorLine(colorLine)
            gradient = CG.CGGradientCreateWithColors(_sRGBColorSpace, colors, stops)
            CG.CGContextDrawLinearGradient(
                self.context,
                gradient,
                pt1,
                pt2,
                CG.kCGGradientDrawsBeforeStartLocation
                | CG.kCGGradientDrawsAfterEndLocation,
            )

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
        if self._shouldNotDrawPath(path):
            return
        with self.savedState():
            if path is not None:
                CG.CGContextAddPath(self.context, path.path)
                CG.CGContextClip(self.context)
            # else: unbounded source, paint the existing clip area
            self.transform(gradientTransform)
            if extendMode in (ExtendMode.REPEAT, ExtendMode.REFLECT):
                colorLine, startCenter, startRadius, endCenter, endRadius = (
                    _expandRadialGradient(
                        self.context,
                        colorLine,
                        startCenter,
                        startRadius,
                        endCenter,
                        endRadius,
                        extendMode,
                    )
                )
            colors, stops = _unpackColorLine(colorLine)
            gradient = CG.CGGradientCreateWithColors(_sRGBColorSpace, colors, stops)
            CG.CGContextDrawRadialGradient(
                self.context,
                gradient,
                startCenter,
                startRadius,
                endCenter,
                endRadius,
                CG.kCGGradientDrawsBeforeStartLocation
                | CG.kCGGradientDrawsAfterEndLocation,
            )

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
        if self._shouldNotDrawPath(path):
            return
        with self.savedState():
            if path is not None:
                CG.CGContextAddPath(self.context, path.path)
                CG.CGContextClip(self.context)
            # else: unbounded source, paint the existing clip area
            self.transform(gradientTransform)
            # find current path' extent
            (x1, y1), (w, h) = CG.CGContextGetClipBoundingBox(self.context)
            x2 = x1 + w
            y2 = y1 + h
            maxX = max(d * d for d in (x1 - center[0], x2 - center[0]))
            maxY = max(d * d for d in (y1 - center[1], y2 - center[1]))
            R = sqrt(maxX + maxY)
            # compute the triangle fan approximating the sweep gradient
            patches = buildSweepGradientPatches(
                colorLine,
                center,
                R,
                startAngle,
                endAngle,
                useGouraudShading=True,
                extendMode=extendMode,
            )
            if not patches:
                return
            CG.CGContextBeginTransparencyLayer(self.context, None)
            CG.CGContextSetBlendMode(self.context, CG.kCGBlendModeCopy)
            CG.CGContextSetAllowsAntialiasing(self.context, False)
            for (P0, color0), (P1, color1) in patches:
                color = 0.5 * (color0 + color1)
                CG.CGContextMoveToPoint(self.context, center[0], center[1])
                CG.CGContextAddLineToPoint(self.context, P0[0], P0[1])
                CG.CGContextAddLineToPoint(self.context, P1[0], P1[1])
                CG.CGContextSetFillColorWithColor(
                    self.context, CG.CGColorCreate(_sRGBColorSpace, color)
                )
                CG.CGContextFillPath(self.context)
            CG.CGContextSetAllowsAntialiasing(self.context, True)
            CG.CGContextEndTransparencyLayer(self.context)

    def _shouldNotDrawPath(self, path):
        return self.clipIsEmpty or (
            path is not None and CG.CGPathGetBoundingBox(path.path) == CG.CGRectNull
        )


def _unpackColorLine(colorLine):
    colors = []
    stops = []
    for stop, color in colorLine:
        colors.append(CG.CGColorCreate(_sRGBColorSpace, color))
        stops.append(stop)
    return colors, stops


def _expandLinearGradient(context, colorLine, pt1, pt2, extendMode):
    """Expand a linear gradient's color line and endpoints to simulate
    REPEAT or REFLECT extend modes, which CoreGraphics doesn't support natively.
    """
    # Get clip bounds in gradient space (after gradientTransform was applied)
    (bx, by), (bw, bh) = CG.CGContextGetClipBoundingBox(context)
    corners = [(bx, by), (bx + bw, by), (bx, by + bh), (bx + bw, by + bh)]

    # Compute gradient direction vector
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    lenSq = dx * dx + dy * dy
    if lenSq < 1e-10:
        return colorLine, pt1, pt2

    # Project clip box corners onto gradient axis to find t range
    tValues = []
    for cx, cy in corners:
        t = ((cx - pt1[0]) * dx + (cy - pt1[1]) * dy) / lenSq
        tValues.append(t)
    tMin = min(tValues)
    tMax = max(tValues)

    # Determine repetition range
    repMin = int(tMin) - 1 if tMin < 0 else 0
    repMax = int(tMax) + 1 if tMax > 1 else 1
    numReps = repMax - repMin

    if numReps <= 1:
        return colorLine, pt1, pt2

    # Build expanded color line
    newColorLine = []
    for i in range(repMin, repMax):
        repIndex = i - repMin
        if extendMode == ExtendMode.REFLECT and i % 2 != 0:
            # Reversed
            for stop, color in reversed(colorLine):
                newStop = (repIndex + (1 - stop)) / numReps
                newColorLine.append((newStop, color))
        else:
            for stop, color in colorLine:
                newStop = (repIndex + stop) / numReps
                newColorLine.append((newStop, color))

    # Expand endpoints
    newPt1 = (
        pt1[0] + repMin * dx,
        pt1[1] + repMin * dy,
    )
    newPt2 = (
        pt1[0] + repMax * dx,
        pt1[1] + repMax * dy,
    )

    return newColorLine, newPt1, newPt2


def _expandRadialGradient(
    context, colorLine, startCenter, startRadius, endCenter, endRadius, extendMode
):
    """Expand a radial gradient's color line and parameters to simulate
    REPEAT or REFLECT extend modes, which CoreGraphics doesn't support natively.

    Extends both inward (t < 0) and outward (t > 1) to cover the visible area.
    """
    (bx, by), (bw, bh) = CG.CGContextGetClipBoundingBox(context)
    corners = [(bx, by), (bx + bw, by), (bx, by + bh), (bx + bw, by + bh)]

    radiusDiff = endRadius - startRadius
    centerDx = endCenter[0] - startCenter[0]
    centerDy = endCenter[1] - startCenter[1]

    if abs(radiusDiff) < 1e-10 and (centerDx * centerDx + centerDy * centerDy) < 1e-10:
        return colorLine, startCenter, startRadius, endCenter, endRadius

    # Max distance from gradient start center to any clip corner
    maxDist = 0
    for cx, cy in corners:
        dist = sqrt((cx - startCenter[0]) ** 2 + (cy - startCenter[1]) ** 2)
        maxDist = max(maxDist, dist)

    # Forward reps needed (t > 1)
    if abs(radiusDiff) > 1e-10:
        repMax = int(ceil(maxDist / abs(radiusDiff))) + 1
    else:
        centerDist = sqrt(centerDx * centerDx + centerDy * centerDy)
        repMax = int(ceil(maxDist / centerDist)) + 1 if centerDist > 1e-10 else 1

    # Backward reps needed (t < 0) — only extend inward to where radius
    # is still positive; stop before it would go to 0 to avoid distorting
    # the geometry (CG clamps negative radii, breaking the interpolation)
    repMin = 0
    if startRadius > 0 and abs(radiusDiff) > 1e-10:
        # t where radius=0: t_zero = -startRadius / radiusDiff
        # Only extend to integer reps that keep radius positive
        t_zero = -startRadius / radiusDiff
        if t_zero < 0:
            repMin = int(t_zero)  # truncate toward zero (e.g. -1.33 → -1)

    repMax = min(repMax, 50)
    repMin = max(repMin, -50)
    totalReps = repMax - repMin

    if totalReps <= 1:
        return colorLine, startCenter, startRadius, endCenter, endRadius

    # Build expanded color line covering [repMin, repMax)
    newColorLine = []
    for i in range(repMin, repMax):
        idx = i - repMin
        if extendMode == ExtendMode.REFLECT and i % 2 != 0:
            for stop, color in reversed(colorLine):
                newColorLine.append(((idx + (1 - stop)) / totalReps, color))
        else:
            for stop, color in colorLine:
                newColorLine.append(((idx + stop) / totalReps, color))

    def _lerp(a, b, t):
        return a + t * (b - a)

    newStartCenter = (
        _lerp(startCenter[0], endCenter[0], repMin),
        _lerp(startCenter[1], endCenter[1], repMin),
    )
    newStartRadius = max(0, _lerp(startRadius, endRadius, repMin))
    newEndCenter = (
        _lerp(startCenter[0], endCenter[0], repMax),
        _lerp(startCenter[1], endCenter[1], repMax),
    )
    newEndRadius = max(0, _lerp(startRadius, endRadius, repMax))

    return newColorLine, newStartCenter, newStartRadius, newEndCenter, newEndRadius


class CoreGraphicsPixelSurface(Surface):
    fileExtension = ".png"

    def __init__(self):
        self.context = None

    @contextmanager
    def canvas(self, boundingBox):
        x, y, xMax, yMax = boundingBox
        width = xMax - x
        height = yMax - y
        self._setupCGContext(x, y, width, height)
        yield CoreGraphicsCanvas(self.context)

    def _setupCGContext(self, x, y, width, height):
        self.context = CG.CGBitmapContextCreate(
            None,
            width,
            height,
            8,
            0,
            _sRGBColorSpace,
            CG.kCGImageAlphaPremultipliedFirst,
        )
        CG.CGContextTranslateCTM(self.context, -x, -y)

    def saveImage(self, path):
        image = CG.CGBitmapContextCreateImage(self.context)
        saveImageAsPNG(image, path)


class CoreGraphicsPDFSurface(CoreGraphicsPixelSurface):
    fileExtension = ".pdf"

    @contextmanager
    def canvas(self, boundingBox):
        with super().canvas(boundingBox) as canvas:
            CG.CGContextBeginPage(self.context, self._mediaBox)
            try:
                yield canvas
            finally:
                CG.CGContextEndPage(self.context)

    def _setupCGContext(self, x, y, width, height):
        if self.context is None:
            self._mediaBox = ((x, y), (width, height))
            self._data = CFDataCreateMutable(None, 0)
            consumer = CG.CGDataConsumerCreateWithCFData(self._data)
            self.context = CG.CGPDFContextCreate(consumer, self._mediaBox, None)
        return self.context

    def saveImage(self, path):
        CG.CGPDFContextClose(self.context)
        with open(path, "wb") as f:
            f.write(self._data)


def saveImageAsPNG(image, path):
    path = os.path.abspath(path).encode("utf-8")
    url = CG.CFURLCreateFromFileSystemRepresentation(None, path, len(path), False)
    assert url is not None
    dest = CG.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    assert dest is not None
    CG.CGImageDestinationAddImage(dest, image, None)
    CG.CGImageDestinationFinalize(dest)
