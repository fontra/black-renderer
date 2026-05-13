from compareImages import compareImages


def test_compareImagesRendersEquivalentSVGSerialization(tmp_path):
    expected = tmp_path / "expected.svg"
    output = tmp_path / "output.svg"

    expected.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="20">
<rect x="0" y="0" width="10" height="20" fill="red"/>
</svg>
""",
        encoding="utf-8",
    )
    output.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="20" version="1.1">
<g id="surface123">
<rect style="stroke:none;fill:red;" x="0" y="0" width="10" height="20"/>
</g>
</svg>
""",
        encoding="utf-8",
    )

    assert compareImages(expected, output) == 0


def test_compareImagesDetectsRenderedSVGDifferences(tmp_path):
    expected = tmp_path / "expected.svg"
    output = tmp_path / "output.svg"

    expected.write_text(_svgWithFill("red"), encoding="utf-8")
    output.write_text(_svgWithFill("blue"), encoding="utf-8")

    assert compareImages(expected, output) > 0


def _svgWithFill(fill):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="20">
<rect x="0" y="0" width="10" height="20" fill="{fill}"/>
</svg>
"""
