from collections import UserList
from contextlib import contextmanager
from io import BytesIO
import logging
import math
from fontTools.misc.transform import Transform, Identity
from fontTools.misc.arrayTools import unionRect
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import (
    BaseTable,
    ClipBoxFormat,
    CompositeMode,
    Paint,
    PaintFormat,
    VarAffine2x3,
    VarColorStop,
    VarColorLine,
)
from fontTools.varLib.varStore import VarStoreInstancer
import uharfbuzz as hb

logger = logging.getLogger(__name__)


PAINT_NAMES = {v.value: k for k, v in PaintFormat.__members__.items()}
PAINT_VAR_MAPPING = {
    # Map PaintVarXxx Format to its corresponding non-var Format
    v.value: PaintFormat[k.replace("PaintVar", "Paint")]
    for k, v in PaintFormat.__members__.items()
    if k.startswith("PaintVar")
}


class BlackRendererFont:
    def __init__(self, path=None, *, fontNumber=0, lazy=True, ttFont=None, hbFont=None):
        if path is not None:
            if ttFont is not None or hbFont is not None:
                raise TypeError("either pass 'path', or both 'ttFont' and 'hbFont")

            with open(path, "rb") as f:
                fontData = f.read()
            self.ttFont = TTFont(BytesIO(fontData), fontNumber=fontNumber, lazy=lazy)
            self.hbFont = hb.Font(hb.Face(fontData, fontNumber))
        else:
            if ttFont is None or hbFont is None:
                raise TypeError("either pass 'path', or both 'ttFont' and 'hbFont")

            self.ttFont = ttFont
            self.hbFont = hbFont

        self.textColor = (0, 0, 0, 1)
        self.colrV0Glyphs = {}
        self.colrV1Glyphs = {}
        self.instancer = None
        self.varIndexMap = None

        if "COLR" in self.ttFont:
            colrTable = self.ttFont["COLR"]
            if colrTable.version == 0:
                self.colrV0Glyphs = colrTable.ColorLayers
            else:  # >= 1
                # Hm, a little sad we need to use an internal static method
                self.colrV0Glyphs = colrTable._decompileColorLayersV0(colrTable.table)
                colrTable = colrTable.table
                self.colrV1Glyphs = {
                    glyph.BaseGlyph: glyph
                    for glyph in colrTable.BaseGlyphList.BaseGlyphPaintRecord
                }
                if colrTable.ClipList is None:
                    self.clipBoxes = None
                else:
                    self.clipBoxes = colrTable.ClipList.clips
                self.colrLayersV1 = colrTable.LayerList
                if colrTable.VarStore is not None:
                    if colrTable.VarIndexMap:
                        self.varIndexMap = colrTable.VarIndexMap.mapping
                    self.instancer = VarStoreInstancer(
                        colrTable.VarStore, self.ttFont["fvar"].axes
                    )
                else:
                    self.instancer = None

        if "CPAL" in self.ttFont:
            self.palettes = _unpackPalettes(self.ttFont["CPAL"].palettes)
            self.currentPalette = self.palettes[0]
        else:
            self.palettes = None
            self.currentPalette = None

        if "fvar" in self.ttFont:
            self.axisTags = [a.axisTag for a in self.ttFont["fvar"].axes]
        else:
            self.axisTags = []

    @property
    def unitsPerEm(self):
        return self.hbFont.face.upem

    def getPalette(self, paletteIndex):
        if not self.palettes:
            return None
        # clamp index
        paletteIndex = max(0, min(paletteIndex, len(self.palettes) - 1))
        return self.palettes[paletteIndex]

    def setLocation(self, location):
        if location is None:
            location = {}
        self.hbFont.set_variations(location)
        if self.instancer is not None:
            normalizedAxisValues = self.hbFont.get_var_coords_normalized()
            normalizedLocation = axisValuesToLocation(
                normalizedAxisValues, self.axisTags
            )
            self.instancer.setLocation(normalizedLocation)

    @property
    def glyphNames(self):
        return self.ttFont.getGlyphOrder()

    @property
    def colrV0GlyphNames(self):
        return self.colrV0Glyphs.keys()

    @property
    def colrV1GlyphNames(self):
        return self.colrV1Glyphs.keys()

    def getGlyphBounds(self, glyphName):
        if glyphName in self.colrV1Glyphs:
            bounds = self._getGlyphBounds(glyphName)
            if self.clipBoxes is not None:
                box = self.clipBoxes.get(glyphName)
                if box is not None:
                    if (
                        box.Format == ClipBoxFormat.Variable
                        and self.instancer is not None
                    ):
                        box = VarTableWrapper(box, self.instancer, self.varIndexMap)
                    bounds = box.xMin, box.yMin, box.xMax, box.yMax
        elif glyphName in self.colrV0Glyphs:
            # For COLRv0, we take the union of all layer bounds
            bounds = None
            for layer in self.colrV0Glyphs[glyphName]:
                layerBounds = self._getGlyphBounds(layer.name)
                if bounds is None:
                    bounds = layerBounds
                else:
                    bounds = unionRect(layerBounds, bounds)
        else:
            bounds = self._getGlyphBounds(glyphName)
        return bounds

    def drawGlyph(self, glyphName, canvas, *, palette=None, textColor=(0, 0, 0, 1)):
        if palette is None and self.palettes:
            palette = self.palettes[0]
        self.currentPalette = palette
        self.textColor = textColor
        self._recursionCheck = set()

        glyph = self.colrV1Glyphs.get(glyphName)
        if glyph is not None:
            self.currentTransform = Identity
            self.currentPath = None
            self._drawGlyphCOLRv1(glyph, canvas)
            return
        glyph = self.colrV0Glyphs.get(glyphName)
        if glyph is not None:
            self._drawGlyphCOLRv0(glyph, canvas)
            return
        else:
            self._drawGlyphNoColor(glyphName, canvas)

    def _drawGlyphNoColor(self, glyphName, canvas):
        path = canvas.newPath()
        self._drawGlyphOutline(glyphName, path)
        canvas.drawPathSolid(path, self.textColor)

    def _drawGlyphCOLRv0(self, layers, canvas):
        for layer in layers:
            path = canvas.newPath()
            self._drawGlyphOutline(layer.name, path)
            canvas.drawPathSolid(path, self._getColor(layer.colorID, 1))

    def _drawGlyphCOLRv1(self, glyph, canvas):
        if glyph.BaseGlyph in self._recursionCheck:
            raise RecursionError(f"Glyph '{glyph.BaseGlyph}' references itself")
        self._recursionCheck.add(glyph.BaseGlyph)
        try:
            self._drawPaint(glyph.Paint, canvas)
        finally:
            self._recursionCheck.remove(glyph.BaseGlyph)

    # COLRv1 Paint dispatch

    def _drawPaint(self, paint, canvas):
        nonVarFormat = PAINT_VAR_MAPPING.get(paint.Format)
        if nonVarFormat is None:
            # "regular" Paint
            paintName = PAINT_NAMES.get(paint.Format)
            if paintName is None:
                logger.warning(f"Ignoring unknown COLRv1 Paint format: {paint.Format}")
                return
        else:
            # PaintVar -- we map to its non-var counterpart and use a wrapper
            # that takes care of instantiating values
            paintName = PAINT_NAMES[nonVarFormat]
            paint = VarTableWrapper(paint, self.instancer, self.varIndexMap)
        drawHandler = getattr(self, "_draw" + paintName)
        drawHandler(paint, canvas)

    def _drawPaintColrLayers(self, paint, canvas):
        n = paint.NumLayers
        s = paint.FirstLayerIndex
        with self._ensureClipAndPushPath(canvas, None):
            for i in range(s, s + n):
                with self._savedTransform():
                    self._drawPaint(self.colrLayersV1.Paint[i], canvas)

    def _drawPaintSolid(self, paint, canvas):
        color = self._getColor(paint.PaletteIndex, paint.Alpha)
        canvas.drawPathSolid(self.currentPath, color)

    def _drawPaintLinearGradient(self, paint, canvas):
        minStop, maxStop, colorLine = self._readColorLine(paint.ColorLine)
        pt1, pt2 = _reduceThreeAnchorsToTwo(paint)
        pt1, pt2 = (
            _interpolatePoints(pt1, pt2, minStop),
            _interpolatePoints(pt1, pt2, maxStop),
        )
        canvas.drawPathLinearGradient(
            self.currentPath,
            colorLine,
            pt1,
            pt2,
            paint.ColorLine.Extend,
            self.currentTransform,
        )

    def _drawPaintRadialGradient(self, paint, canvas):
        minStop, maxStop, colorLine = self._readColorLine(paint.ColorLine)
        startCenter = (paint.x0, paint.y0)
        endCenter = (paint.x1, paint.y1)
        startCenter, endCenter = (
            _interpolatePoints(startCenter, endCenter, minStop),
            _interpolatePoints(startCenter, endCenter, maxStop),
        )
        startRadius = _interpolate(paint.r0, paint.r1, minStop)
        endRadius = _interpolate(paint.r0, paint.r1, maxStop)
        canvas.drawPathRadialGradient(
            self.currentPath,
            colorLine,
            startCenter,
            startRadius,
            endCenter,
            endRadius,
            paint.ColorLine.Extend,
            self.currentTransform,
        )

    def _drawPaintSweepGradient(self, paint, canvas):
        minStop, maxStop, colorLine = self._readColorLine(paint.ColorLine)
        center = paint.centerX, paint.centerY
        startAngle = _interpolate(paint.startAngle, paint.endAngle, minStop)
        endAngle = _interpolate(paint.startAngle, paint.endAngle, maxStop)
        canvas.drawPathSweepGradient(
            self.currentPath,
            colorLine,
            center,
            startAngle,
            endAngle,
            paint.ColorLine.Extend,
            self.currentTransform,
        )

    def _drawPaintGlyph(self, paint, canvas):
        path = canvas.newPath()
        # paint.Glyph must not be a COLR glyph
        self._drawGlyphOutline(paint.Glyph, path)
        with self._ensureClipAndPushPath(canvas, path):
            self._drawPaint(paint.Paint, canvas)

    def _drawPaintColrGlyph(self, paint, canvas):
        with self._ensureClipAndPushPath(canvas, None):
            self._drawGlyphCOLRv1(self.colrV1Glyphs[paint.Glyph], canvas)

    def _drawPaintTransform(self, paint, canvas):
        t = paint.Transform
        transform = (t.xx, t.yx, t.xy, t.yy, t.dx, t.dy)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintTranslate(self, paint, canvas):
        transform = (1, 0, 0, 1, paint.dx, paint.dy)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintRotate(self, paint, canvas):
        transform = Transform()
        transform = transform.rotate(math.radians(paint.angle))
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintRotateAroundCenter(self, paint, canvas):
        transform = Transform()
        transform = transform.translate(paint.centerX, paint.centerY)
        transform = transform.rotate(math.radians(paint.angle))
        transform = transform.translate(-paint.centerX, -paint.centerY)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintSkew(self, paint, canvas):
        transform = Transform()
        transform = transform.skew(
            -math.radians(paint.xSkewAngle), math.radians(paint.ySkewAngle)
        )
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintSkewAroundCenter(self, paint, canvas):
        transform = Transform()
        transform = transform.translate(paint.centerX, paint.centerY)
        transform = transform.skew(
            -math.radians(paint.xSkewAngle), math.radians(paint.ySkewAngle)
        )
        transform = transform.translate(-paint.centerX, -paint.centerY)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintScale(self, paint, canvas):
        transform = Transform()
        transform = transform.scale(paint.scaleX, paint.scaleY)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintScaleAroundCenter(self, paint, canvas):
        transform = Transform()
        transform = transform.translate(paint.centerX, paint.centerY)
        transform = transform.scale(paint.scaleX, paint.scaleY)
        transform = transform.translate(-paint.centerX, -paint.centerY)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintScaleUniform(self, paint, canvas):
        transform = Transform()
        transform = transform.scale(paint.scale, paint.scale)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintScaleUniformAroundCenter(self, paint, canvas):
        transform = Transform()
        transform = transform.translate(paint.centerX, paint.centerY)
        transform = transform.scale(paint.scale, paint.scale)
        transform = transform.translate(-paint.centerX, -paint.centerY)
        self._applyTransform(transform, paint.Paint, canvas)

    def _drawPaintComposite(self, paint, canvas):
        with self._ensureClipAndPushPath(canvas, None):
            with canvas.compositeMode(CompositeMode.SRC_OVER):
                with self._savedTransform():
                    self._drawPaint(paint.BackdropPaint, canvas)
                with canvas.compositeMode(paint.CompositeMode):
                    with self._savedTransform():
                        self._drawPaint(paint.SourcePaint, canvas)

    def _drawPaintLocation(self, paint, canvas):
        # https://github.com/googlefonts/colr-gradients-spec/issues/277
        numAxes = len(self.axisTags)
        location = {
            self.axisTags[coord.AxisIndex]: coord.AxisValue
            for coord in paint.Coordinate
            if coord.AxisIndex < numAxes
        }
        with self._pushNormalizedLocation(location):
            self._drawPaint(paint.Paint, canvas)

    # Utils

    @contextmanager
    def _pushNormalizedLocation(self, location):
        savedAxisValues = self.hbFont.get_var_coords_normalized()
        tmpAxisValues = list(savedAxisValues)
        if len(tmpAxisValues) < len(self.axisTags):
            # pad with zeros
            tmpAxisValues.extend([0] * (len(self.axisTags) - len(tmpAxisValues)))
        for axisIndex, axisTag in enumerate(self.axisTags):
            axisValue = location.get(axisTag)
            if axisValue is not None:
                tmpAxisValues[axisIndex] = axisValue
        tmpLocation = axisValuesToLocation(tmpAxisValues, self.axisTags)

        self.hbFont.set_var_coords_normalized(tmpAxisValues)
        if self.instancer is not None:
            savedLocation = self.instancer.location
            # FIXME: calling setLocation loses the internal instancer._scalars cache;
            # perhaps a pushing a *new* instancer and reverting to the old one is
            # faster, but this is currently not possible due to PaintVarXxx referencing
            # self.instancer, too.
            self.instancer.setLocation(tmpLocation)
            yield
            self.instancer.setLocation(savedLocation)
        else:
            yield
        self.hbFont.set_var_coords_normalized(savedAxisValues)

    @contextmanager
    def _ensureClipAndPushPath(self, canvas, path):
        currentPath = self.currentPath
        currentTransform = self.currentTransform
        self.currentPath = path
        self.currentTransform = Identity
        with canvas.savedState():
            if currentPath is not None:
                canvas.clipPath(currentPath)
            if currentTransform != Identity:
                canvas.transform(currentTransform)
            yield
        self.currentPath = currentPath
        self.currentTransform = currentTransform

    @contextmanager
    def _savedTransform(self):
        savedTransform = self.currentTransform
        yield
        self.currentTransform = savedTransform

    def _applyTransform(self, transform, paint, canvas):
        self.currentTransform = self.currentTransform.transform(transform)
        self._drawPaint(paint, canvas)

    def _drawGlyphOutline(self, glyphName, path):
        gid = self.ttFont.getGlyphID(glyphName)
        self.hbFont.draw_glyph_with_pen(gid, path)

    def _getGlyphBounds(self, glyphName):
        gid = self.ttFont.getGlyphID(glyphName)
        assert gid is not None, glyphName
        x, y, w, h = self.hbFont.get_glyph_extents(gid)
        # convert from HB's x/y_bearing + extents to xMin, yMin, xMax, yMax
        y += h
        h = -h
        w += x
        h += y
        return x, y, w, h

    def _getColor(self, colorIndex, alpha):
        if (
            colorIndex == 0xFFFF
            or self.currentPalette is None
            or colorIndex >= len(self.currentPalette)
        ):
            r, g, b, a = self.textColor
        else:
            r, g, b, a = self.currentPalette[colorIndex]
        a *= alpha
        return r, g, b, a

    def _readColorLine(self, colorLineTable):
        return _normalizeColorLine(
            [
                (cs.StopOffset, self._getColor(cs.PaletteIndex, cs.Alpha))
                for cs in colorLineTable.ColorStop
            ]
        )


def _reduceThreeAnchorsToTwo(p):
    # FIXME: make sure the 3 points are not in degenerate position [see COLRv1 spec].
    x02 = p.x2 - p.x0
    y02 = p.y2 - p.y0
    x01 = p.x1 - p.x0
    y01 = p.y1 - p.y0
    squaredNorm02 = x02 * x02 + y02 * y02
    if squaredNorm02 < 0.000001:
        return ((p.x0, p.y0), (p.x1, p.y1))
    k = (x01 * x02 + y01 * y02) / squaredNorm02
    x = p.x1 - k * x02
    y = p.y1 - k * y02
    return ((p.x0, p.y0), (x, y))


def _normalizeColorLine(colorLine):
    stops = [stopOffset for stopOffset, color in colorLine]
    minStop = min(stops)
    maxStop = max(stops)
    if minStop != maxStop:
        stopExtent = maxStop - minStop
        colorLine = [
            ((stopOffset - minStop) / stopExtent, color)
            for stopOffset, color in colorLine
        ]
    else:
        # Degenerate case. minStop and maxStop are used to reposition
        # the gradients parameters (points, radii, angles), through
        # interpolation. By setting minStop and maxStop to 0 and 1,
        # we at least won't mess up the parameters.
        # FIXME: should the gradient simply not be drawn in this case?
        # 1. If there's only one color stop, we can just draw a solid
        # color.
        # 2. If there are > 1 color stops all at the same color stop
        # offset, things get interesting: everything "to the left"
        # should get color[0], everything "to the right" should get
        # color[-1]. If there are more than 2 color stops, all but the
        # first and last should be ignored.
        minStop, maxStop = 0, 1
    return minStop, maxStop, colorLine


def _interpolate(v1, v2, f):
    return v1 + f * (v2 - v1)


def _interpolatePoints(pt1, pt2, f):
    x1, y1 = pt1
    x2, y2 = pt2
    return (x1 + f * (x2 - x1), y1 + f * (y2 - y1))


def _unpackPalettes(palettes):
    return [
        [(c.red / 255, c.green / 255, c.blue / 255, c.alpha / 255) for c in p]
        for p in palettes
    ]


def axisValuesToLocation(normalizedAxisValues, axisTags):
    return {
        axisTag: axisValue for axisTag, axisValue in zip(axisTags, normalizedAxisValues)
    }


class VarTableWrapper:
    def __init__(self, wrapped, instancer, varIndexMap=None):
        assert not isinstance(wrapped, VarTableWrapper)
        self._wrapped = wrapped
        self._instancer = instancer
        self._varIndexMap = varIndexMap
        # Map {attrName: varIndexOffset}, where the offset is a number to add to
        # VarIndexBase to get to the VarIndex associated with each attribute.
        # getVariableAttrs method returns a sequence of variable attributes in the
        # order in which they appear in a table.
        # E.g. in ColorStop table, the first variable attribute is "StopOffset",
        # and the second is "Alpha": hence the StopOffset's VarIndex is computed as
        # VarIndexBase + 0, Alpha's is VarIndexBase + 1, etc.
        self._varAttrs = {a: i for i, a in enumerate(wrapped.getVariableAttrs())}

    def __repr__(self):
        return f"VarTableWrapper({self._wrapped!r})"

    def _getVarIndexForAttr(self, attrName):
        if attrName not in self._varAttrs:
            return None

        baseIndex = self._wrapped.VarIndexBase
        if baseIndex == 0xFFFFFFFF:
            return baseIndex

        offset = self._varAttrs[attrName]
        varIdx = baseIndex + offset
        if self._varIndexMap is not None:
            try:
                varIdx = self._varIndexMap[varIdx]
            except IndexError:
                pass

        return varIdx

    def _getDeltaForAttr(self, attrName, varIdx):
        delta = self._instancer[varIdx]
        # deltas for Fixed or F2Dot14 need to be converted from int to float
        conv = self._wrapped.getConverterByName(attrName)
        if hasattr(conv, "fromInt"):
            delta = conv.fromInt(delta)
        return delta

    def __getattr__(self, attrName):
        value = getattr(self._wrapped, attrName)

        varIdx = self._getVarIndexForAttr(attrName)
        if varIdx is not None:
            if varIdx < 0xFFFFFFFF:
                value += self._getDeltaForAttr(attrName, varIdx)
        elif isinstance(value, (VarAffine2x3, VarColorLine)):
            value = VarTableWrapper(value, self._instancer, self._varIndexMap)
        elif (
            isinstance(value, (list, UserList))
            and value
            and isinstance(value[0], VarColorStop)
        ):
            value = [
                VarTableWrapper(item, self._instancer, self._varIndexMap)
                for item in value
            ]

        return value
