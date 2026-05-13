from abc import ABC, abstractmethod
from contextlib import contextmanager


class Canvas(ABC):
    @abstractmethod
    def newPath(self):
        pass

    @abstractmethod
    @contextmanager
    def savedState(self):
        pass

    @abstractmethod
    @contextmanager
    def compositeMode(self, compositeMode):
        pass

    @abstractmethod
    def transform(self, transform):
        pass

    @abstractmethod
    def clipPath(self, path):
        pass

    @abstractmethod
    def drawPathSolid(self, path, color):
        pass

    @abstractmethod
    def drawPathLinearGradient(
        self, path, colorLine, pt1, pt2, extendMode, gradientTransform
    ):
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    # Generic convenience methods

    def translate(self, x, y):
        self.transform((1, 0, 0, 1, x, y))

    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        self.transform((sx, 0, 0, sy, 0, 0))

    def drawRectSolid(self, rect, color):
        self.drawPathSolid(self._rectPath(rect), color)

    def drawRectLinearGradient(self, rect, *args, **kwargs):
        self.drawPathLinearGradient(self._rectPath(rect), *args, **kwargs)

    def drawRectRadialGradient(self, rect, *args, **kwargs):
        self.drawPathRadialGradient(self._rectPath(rect), *args, **kwargs)

    def drawRectSweepGradient(self, rect, *args, **kwargs):
        self.drawPathSweepGradient(self._rectPath(rect), *args, **kwargs)

    def _rectPath(self, rect):
        x, y, w, h = rect
        path = self.newPath()
        path.moveTo((x, y))
        path.lineTo((x, y + h))
        path.lineTo((x + w, y + h))
        path.lineTo((x + w, y))
        path.closePath()
        return path


class Surface(ABC):
    fileExtension = ".png"

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    @contextmanager
    def canvas(self, boundingBox):
        # boundingBox = (xMin, yMin, xMax, yMax)
        pass

    @abstractmethod
    def saveImage(self, path):
        pass
