import pathlib
from blackrenderer.font import BlackRendererFont

testDir = pathlib.Path(__file__).resolve().parent
testFont1 = testDir / "data" / "noto-glyf_colr_1.ttf"


def test_font():
    font = BlackRendererFont(testFont1)
    assert len(font.glyphNames) > len(font.colrV0GlyphNames)
    assert len(font.glyphNames) > len(font.colrV1GlyphNames)
