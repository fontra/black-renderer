import pathlib
from blackrenderer.font import BlackRendererFont
from blackrenderer.dumpCOLRv1Glyph import dumpCOLRv1Glyph


testDir = pathlib.Path(__file__).resolve().parent
testFont1 = testDir / "data" / "noto-glyf_colr_1.ttf"


expected_output = """\
uni2693
  # PaintColrLayers
  Layers
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 2172
          Alpha 1.0
      Glyph glyph21626
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 877
          Alpha 1.0
      Glyph glyph21627
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 2517
          Alpha 1.0
      Glyph glyph21628
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 877
          Alpha 0.89
      Glyph glyph21629
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 2517
          Alpha 1.0
      Glyph glyph21630
    - # PaintGlyph
      Format 10
      Paint
          # PaintSolid
          Format 2
          PaletteIndex 877
          Alpha 1.0
      Glyph glyph21631
"""


def test_dump(capsys):
    font = BlackRendererFont(testFont1)
    dumpCOLRv1Glyph(font, "uni2693")
    captured = capsys.readouterr()
    assert expected_output == captured.out
