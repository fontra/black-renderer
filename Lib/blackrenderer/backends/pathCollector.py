from contextlib import contextmanager
from fontTools.misc.arrayTools import calcBounds
from fontTools.misc.transform import Identity
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from .base import Canvas


class PathCollectorCanvas(Canvas):
    def __init__(self):
        self.init()

    def init(self):
        self.paths = []
        self.currentTransform = Identity

    def _addPath(self, path):
        if self.currentTransform != Identity:
            path = transformPath(path, self.currentTransform)
        self.paths.append(path)

    def newPath(self):
        return RecordingPen()

    @contextmanager
    def savedState(self):
        savedTransform = self.currentTransform
        yield
        self.currentTransform = savedTransform

    @contextmanager
    def compositeMode(self, compositeMode):
        yield

    def transform(self, transform):
        self.currentTransform = self.currentTransform.transform(transform)

    def clipPath(self, path):
        pass

    def drawPathSolid(self, path, color):
        self._addPath(path)

    def drawPathLinearGradient(
        self, path, colorLine, pt1, pt2, extendMode, gradientTransform
    ):
        self._addPath(path)

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
        self._addPath(path)

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
        self._addPath(path)


class PointCollector:
    def __init__(self):
        self.points = []

    def moveTo(self, pt):
        self.points.append(pt)

    def lineTo(self, pt):
        self.points.append(pt)

    def curveTo(self, *pts):
        self.points.extend(pts)

    qCurveTo = curveTo

    def closePath(self):
        pass

    def endPath(self):
        pass


class BoundsCanvas(PathCollectorCanvas):
    def init(self):
        self.points = []
        self.currentTransform = Identity

    @property
    def bounds(self):
        return calcBounds(self.points)

    def _addPath(self, path):
        points = path.points
        if self.currentTransform != Identity:
            points = self.currentTransform.transformPoints(points)
        self.points.extend(points)

    def newPath(self):
        return PointCollector()


def transformPath(path, transform):
    transformedPath = RecordingPen()
    tpen = TransformPen(transformedPath, transform)
    path.replay(tpen)
    return transformedPath
