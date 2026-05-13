[![Python package](https://github.com/BlackFoundryCom/black-renderer/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackFoundryCom/black-renderer/actions/workflows/ci.yml)

# BlackRenderer

BlackRenderer is a Python-based renderer for OpenType COLR fonts, with multiple
backends. It supports the new COLRv1 format as well as the old COLR format. It
fully supports variable fonts, including variable COLRv1 data.

![Big Smiley Face Icon](https://github.com/BlackFoundryCom/black-renderer/blob/main/smile.png?raw=true)

## Features

- It's a Python library called "blackrenderer"
- It's a command line tool called "blackrenderer"
- Renders individual glyphs or text strings
- Supports multiple graphics backends:
  - Skia
  - Cairo
  - CoreGraphics (macOS)
  - SVG
  - outline extractor
  - bounding box calculator
- Supports multiple output formats:
  - .png
  - .pdf
  - .svg
- It uses fonttools to parse COLRv1 data
- The "blackrenderer" tool is an "hb-view"-like command line app with switchable
  backend. It uses HarfBuzz for shaping

## Tool usage example

BlackRenderer comes with an hb-view-like command line tool, that can be used like this:

    $ blackrenderer font.ttf ABC🤩 output.png --font-size=100

## Library usage examples

There is a high level function to render a text string:

```python
from blackrenderer.render import renderText

renderText("myfont.ttf", "ABC", "output.png")  # or "output.svg"
```

The full `renderText()` signature is:

```python
def renderText(
    fontPath,
    textString,
    outputPath,
    *,
    fontSize=250,
    margin=20,
    features=None,
    variations=None,
    backendName=None,
)
```

For more control, the library exposes two main parts: the BlackRendererFont
class, and a set of backend classes. Each backend provides a Canvas class.
You pass a Canvas instance to a BlackRendererFont instance when drawing a
glyph. Most backends also have a Surface class, which is a generalized
convenience class to produce a canvas for a bitmap (or SVG document) for a
specific box. Here is a minimal example:

```python
from blackrenderer.font import BlackRendererFont
from blackrenderer.backends import getSurfaceClass

brFont = BlackRendererFont("my_colr_font.ttf")
glyphName = "A"
boundingBox = brFont.getGlyphBounds(glyphName)
surfaceClass = getSurfaceClass("skia")
surface = surfaceClass()
with surface.canvas(boundingBox):
    brFont.drawGlyph(glyphName, canvas)
surface.saveImage("image.png")
```

Canvas objects support the following transformation methods:

- `canvas.translate(dx, dy)`
- `canvas.scale(sx, sy)`
- `canvas.transform((xx, yx, xy, yy, dx, dy))`

Save/restore is done with a context manager:

```python
with canvas.savedState():
    canvas.scale(0.3)
    ...draw stuff...
```

## Install

If you have a Python 3 environment set up, then all you need to do is:

    $ pip install blackrenderer

## Install for contributing / setting up an environment

Have Python 3.10 or higher installed.

Open Terminal.

"cd" into the project repo directory.

Create a virtual environment:

- `$ python3 -m venv venv --prompt=black-renderer`

Activate the venv:

- `$ source venv/bin/activate`

(You need to activate the virtual environment for every new terminal session.)

Upgrade pip:

- `$ pip install --upgrade pip`

Install the requirements:

- `$ pip install -r requirements.txt`
- `$ pip install -r requirements-dev.txt`

Install blackrenderer in editable mode:

- `$ pip install -e .`

Run the tests:

- `$ pytest`

## Maintainers: how to release

To cut a release, make an annotated git tag, where the tag is in this format:
v1.2.3, where 1, 2 and 3 represent major, minor and micro version numbers.
You can add "aN" or "bN" or "rc" to mark alpha, beta or "release candidate"
versions. Examples: v1.2.3, v1.2.3b2, v1.2.3a4, v1.2.3rc.

The message for the annotated tag should contain the release notes.

Then use "git push --follow-tags" to trigger the release bot. Example session:

- `$ git tag -a v1.2.3 -m "v1.2.3 -- fixed issue #12345"`
- `$ git push --follow-tags`

This process will create a GitHub release, as well as upload the package to
PyPI.
