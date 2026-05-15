from math import pi, ceil, floor, sin, cos, radians, isclose
from fontTools.misc.vector import Vector
from fontTools.ttLib.tables.otTables import ExtendMode


def buildSweepGradientPatches(
    colorLine,
    center,
    radius,
    startAngle,
    endAngle,
    useGouraudShading,
    maxAngle=None,
    extendMode=None,
):
    """Provides colorful triangular patches that mimic a sweep gradient.

    Together the patches approximate an angular section of a disk of center
    'center' and radius 'radius'.
    The patches respect the color line provided by 'colorLine'.
    The angular section is between 'startAngle' and 'endAngle'.

    For use, in particular, in the Cairo and CoreGraphics backends, since these
    libraries lack the sweep gradient feature.

    useGouraudShading -- If True, build a lot of skinny triangles, expected to
    be constant or Gouraud shaded. If False, build fewer degenerate Coons patches
    (outer boundary is rounded), expected to be used in a "mesh gradient"

    Optional keyword arguments:
    maxAngle -- largest desired angular extent of a single triangular patch.
    extendMode -- ExtendMode (PAD, REPEAT, REFLECT) for areas outside the
        gradient's angle range. If provided, the patches will cover the full
        360° circle."""

    colorLine, startAngle, endAngle = normalizeSweepColorLineAndAngles(
        colorLine, startAngle, endAngle, extendMode
    )
    if not colorLine:
        return []

    return _buildPatches(
        colorLine,
        center,
        radius,
        startAngle,
        endAngle,
        useGouraudShading,
        maxAngle,
    )


def normalizeSweepColorLineAndAngles(colorLine, startAngle, endAngle, extendMode=None):
    colorLine = _normalizeCoincidentStops(colorLine, extendMode)
    if not colorLine:
        return [], 0, 0

    if _anglesCoincident(startAngle, endAngle):
        if extendMode in (ExtendMode.REPEAT, ExtendMode.REFLECT):
            return [], 0, 0
        if extendMode == ExtendMode.PAD:
            return _padColorLineForCoincidentAngles(colorLine, startAngle), 0, 360

    # When endAngle < startAngle, the sweep covers the arc going clockwise.
    # Our backends consume increasing angles, so swap angles and reverse the
    # color line to draw the same color rays.
    if endAngle < startAngle:
        startAngle, endAngle = endAngle, startAngle
        colorLine = [(1.0 - stop, color) for stop, color in reversed(colorLine)]

    if extendMode is not None:
        colorLine = _colorLineForDrawingTurn(
            colorLine, startAngle, endAngle, extendMode
        )
        return colorLine, 0, 360

    return colorLine, startAngle, endAngle


def _normalizeCoincidentStops(colorLine, extendMode):
    if not colorLine:
        return []
    if not all(isclose(stop, colorLine[0][0], abs_tol=1e-9) for stop, _ in colorLine):
        return colorLine
    if extendMode in (ExtendMode.REPEAT, ExtendMode.REFLECT):
        return []
    if extendMode != ExtendMode.PAD:
        return colorLine

    offset = max(0, min(1, colorLine[0][0]))
    firstColor = colorLine[0][1]
    lastColor = colorLine[-1][1]
    return [
        (0, firstColor),
        (offset, firstColor),
        (offset, lastColor),
        (1, lastColor),
    ]


def _anglesCoincident(startAngle, endAngle):
    return isclose(startAngle, endAngle, abs_tol=1e-9)


def _padColorLineForCoincidentAngles(colorLine, startAngle):
    angle = (startAngle % 360) / 360.0
    firstColor = colorLine[0][1]
    lastColor = colorLine[-1][1]
    return [
        (0, firstColor),
        (angle, firstColor),
        (angle, lastColor),
        (1, lastColor),
    ]


def _colorLineForDrawingTurn(colorLine, startAngle, endAngle, extendMode):
    angleRange = endAngle - startAngle
    if angleRange <= 0:
        return []

    t0 = (0 - startAngle) / angleRange
    t1 = (360 - startAngle) / angleRange
    samples = _extendedSegmentSamples(colorLine, t0, t1, extendMode)
    colorLine = [
        ((startAngle + t * angleRange) / 360.0, color)
        for t, color in samples
    ]
    colorLine.sort(key=lambda item: item[0])
    return colorLine


def _extendedSegmentSamples(colorLine, t0, t1, extendMode):
    stops = {t0, t1}
    if extendMode == ExtendMode.PAD:
        stops.update(stop for stop, _ in colorLine if t0 <= stop <= t1)
    elif extendMode == ExtendMode.REPEAT:
        for integer in range(floor(t0) - 1, ceil(t1) + 2):
            stops.add(integer)
            stops.update(integer + stop for stop, _ in colorLine)
    elif extendMode == ExtendMode.REFLECT:
        for integer in range(floor(t0) - 1, ceil(t1) + 2):
            stops.add(integer)
            stops.update(integer + stop for stop, _ in colorLine)
            stops.update(integer + 1 - stop for stop, _ in colorLine)
    samples = []
    for stop in sorted(stop for stop in stops if t0 <= stop <= t1):
        if stop == t0:
            samples.append(
                (stop, _sampleExtendedColorLine(colorLine, stop, extendMode, side=1))
            )
        elif stop == t1:
            samples.append(
                (stop, _sampleExtendedColorLine(colorLine, stop, extendMode, side=-1))
            )
        else:
            samples.append(
                (stop, _sampleExtendedColorLine(colorLine, stop, extendMode, side=-1))
            )
            samples.append(
                (stop, _sampleExtendedColorLine(colorLine, stop, extendMode, side=1))
            )
    return samples


def _sampleExtendedColorLine(colorLine, t, extendMode, side=0):
    if side:
        t += side * 1e-9
    if extendMode == ExtendMode.PAD:
        t = max(0, min(1, t))
    elif extendMode == ExtendMode.REPEAT:
        t = t % 1.0
    elif extendMode == ExtendMode.REFLECT:
        t = t % 2.0
        if t > 1:
            t = 2 - t
    return _sampleColorLine(colorLine, t)


def _sampleColorLine(colorLine, t):
    if t <= colorLine[0][0]:
        return colorLine[0][1]
    if t >= colorLine[-1][0]:
        return colorLine[-1][1]

    for (stop0, color0), (stop1, color1) in zip(colorLine, colorLine[1:]):
        if stop1 < t:
            continue
        if stop1 == stop0:
            return color1
        f = (t - stop0) / (stop1 - stop0)
        return tuple(c0 + f * (c1 - c0) for c0, c1 in zip(color0, color1))
    return colorLine[-1][1]


def _buildPatches(
    colorLine,
    center,
    radius,
    startAngle,
    endAngle,
    useGouraudShading,
    maxAngle,
):
    """Build triangle/Coons patches for the given color line and angle range."""
    patches = []
    # Generate a fan of 'triangular' bezier patches.
    if maxAngle is None:
        if useGouraudShading:
            maxAngle = pi / 360.0
        else:
            maxAngle = pi / 8.0
    else:
        maxAngle = max(min(maxAngle, pi / 2), pi / 360)
    if useGouraudShading:
        # Use a slightly larger radius to make sure that disk with the original
        # radius completely fits within the straight-edged triangles that we
        # will generate
        radius = radius / cos(maxAngle / 2)
    n = len(colorLine)
    center = Vector(center)
    for i in range(n - 1):
        a0, col0 = colorLine[i + 0]
        a1, col1 = colorLine[i + 1]
        if a0 == a1:
            # Two equal stopOffsets add color discontinuities. Nothing to draw.
            continue
        col0 = Vector(col0)
        col1 = Vector(col1)
        a0 = radians(startAngle + a0 * (endAngle - startAngle))
        a1 = radians(startAngle + a1 * (endAngle - startAngle))
        numSplits = int(ceil((a1 - a0) / maxAngle))
        if numSplits <= 0:
            continue
        p0 = Vector((cos(a0), sin(a0)))
        color0 = col0
        for a in range(numSplits):
            k = (a + 1.0) / numSplits
            angle1 = a0 + k * (a1 - a0)
            color1 = col0 + k * (col1 - col0)
            p1 = Vector((cos(angle1), sin(angle1)))
            P0 = center[0] + radius * p0[0], center[1] + radius * p0[1]
            P1 = center[0] + radius * p1[0], center[1] + radius * p1[1]
            # draw patch
            if useGouraudShading:
                patches.append(((P0, color0), (P1, color1)))
            else:
                # Compute cubic Bezier antennas (control points) that
                # approximate the circular arc p0-p1.
                A = (p0 + p1).normalized()
                U = Vector((-A[1], A[0]))  # tangent to circle at A
                C0 = A + ((p0 - A).dot(p0) / U.dot(p0)) * U
                C1 = A + ((p1 - A).dot(p1) / U.dot(p1)) * U
                C0 = center + radius * (C0 + 0.33333 * (C0 - p0))
                C1 = center + radius * (C1 + 0.33333 * (C1 - p1))
                patches.append(((P0, color0), C0, C1, (P1, color1)))
            # move to next patch
            p0 = p1
            color0 = color1
    return patches
