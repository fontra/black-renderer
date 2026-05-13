from math import pi, ceil, sin, cos, radians
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

    # When endAngle < startAngle, the sweep covers the SHORT arc going CW.
    # For our CCW triangle fan, swap angles and reverse the color line so
    # we traverse the same arc in CCW order with reversed colors.
    if endAngle < startAngle:
        startAngle, endAngle = endAngle, startAngle
        colorLine = [(1.0 - stop, color) for stop, color in reversed(colorLine)]

    # Normalize angles to [0, 360) range and ensure startAngle < endAngle
    startAngle %= 360
    endAngle %= 360
    if startAngle >= endAngle:
        endAngle += 360

    angleRange = endAngle - startAngle

    # Extend the color line to cover the full 360° circle if needed
    if extendMode is not None and angleRange < 360:
        colorLine, startAngle, endAngle = _extendColorLineForFullCircle(
            colorLine, startAngle, endAngle, angleRange, extendMode
        )

    return _buildPatches(
        colorLine, center, radius, startAngle, endAngle,
        useGouraudShading, maxAngle,
    )


def _extendColorLineForFullCircle(colorLine, startAngle, endAngle, angleRange, extendMode):
    """Extend the color line to cover a full 360° circle based on the extend mode.

    Returns (newColorLine, newStartAngle, newEndAngle).
    """
    from math import ceil as _ceil

    if extendMode == ExtendMode.PAD:
        firstColor = colorLine[0][1]
        lastColor = colorLine[-1][1]

        # Scale original stops from [0,1] to the fraction of the circle they occupy
        f = angleRange / 360
        newColorLine = []
        for stop, color in colorLine:
            newColorLine.append((stop * f, color))

        # Fill the gap with PAD colors. The split between "PAD to last"
        # and "PAD to first" happens at the angle-wrap point (0°/360°),
        # matching how sweep gradient shaders evaluate t:
        #   t = (angle - startAngle) / angleRange
        #   angles just past endAngle → t > 1 → pad to last color
        #   angles just before startAngle → t < 0 → pad to first color
        #   the wrap at 0°/360° is where t jumps from >1 to <0
        gapStartFrac = f  # = endAngle position in [0, 1]

        # Find where 0°/360° falls relative to the gap
        # Gap covers [endAngle, startAngle + 360] in absolute angle space
        if endAngle % 360 == 0:
            wrapAngle = endAngle
        else:
            wrapAngle = (_ceil(endAngle / 360)) * 360

        if wrapAngle < startAngle + 360:
            # Wrap point falls inside the gap — split there
            wrapFrac = f + (wrapAngle - endAngle) / 360
            # [endAngle → wrapAngle]: last color
            # [wrapAngle → startAngle+360]: first color
            if wrapFrac > gapStartFrac:
                newColorLine.append((gapStartFrac, lastColor))
                newColorLine.append((wrapFrac, lastColor))
            if wrapFrac < 1.0:
                newColorLine.append((wrapFrac, firstColor))
                newColorLine.append((1.0, firstColor))
        else:
            # Wrap point is outside the gap — entire gap is PAD to last
            newColorLine.append((gapStartFrac, lastColor))
            newColorLine.append((1.0, lastColor))

        return newColorLine, startAngle, startAngle + 360

    elif extendMode == ExtendMode.REPEAT:
        numReps = int(_ceil(360 / angleRange))
        newColorLine = []
        for i in range(numReps):
            for stop, color in colorLine:
                newColorLine.append(((i + stop) / numReps, color))

        return newColorLine, startAngle, startAngle + numReps * angleRange

    elif extendMode == ExtendMode.REFLECT:
        numReps = int(_ceil(360 / angleRange))
        newColorLine = []
        for i in range(numReps):
            if i % 2 == 0:
                for stop, color in colorLine:
                    newColorLine.append(((i + stop) / numReps, color))
            else:
                for stop, color in reversed(colorLine):
                    newColorLine.append(((i + (1 - stop)) / numReps, color))

        return newColorLine, startAngle, startAngle + numReps * angleRange

    return colorLine, startAngle, endAngle


def _buildPatches(
    colorLine, center, radius, startAngle, endAngle,
    useGouraudShading, maxAngle,
):
    """Build the actual triangle/Coons patches for the given color line and angle range."""
    patches = []
    # generate a fan of 'triangular' bezier patches, with center 'center' and radius 'radius'
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
            continue  # two equal stopOffset are used to add color discontinuities. Nothing to draw
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
                # compute cubic Bezier antennas (control points) so as to approximate the circular arc p0-p1
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
