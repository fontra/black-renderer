import os
import pathlib
import subprocess
import pytest

dataDir = pathlib.Path(__file__).resolve().parent / "data"


testData = [
    ("ABC", dataDir / "MutatorSans.ttf"),
    ("\u2693\u2694", dataDir / "noto-glyf_colr_1.ttf"),
    ("\u3299", dataDir / "TwemojiMozilla.subset.default.3299.ttf"),
]


@pytest.mark.parametrize("testString, fontPath", testData)
@pytest.mark.parametrize("outputFormat", [".png", ".svg"])
def test_mainprog(tmpdir, testString, fontPath, outputFormat):
    outputPath = os.path.join(tmpdir, "test" + outputFormat)
    args = [
        "blackrenderer",
        os.fspath(fontPath),
        testString,
        outputPath,
        "--font-size",
        "50",
    ]
    subprocess.check_output(args)
    assert os.path.isfile(outputPath)


expectedSVGOutput = """\
<?xml version='1.0' encoding='ASCII'?>
<svg width="42" height="75" preserveAspectRatio="xMinYMin slice" viewBox="-17 -20 42 75" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <path d="M60,0 v700 h40 v-700 h-40 Z" fill="#000000" transform="matrix(0.05,0,0,-0.05,0,35)"/>
</svg>
"""


def test_mainprog_svg_stdout():
    args = [
        "blackrenderer",
        os.fspath(dataDir / "MutatorSans.ttf"),
        "I",
        "-",
        "--font-size",
        "50",
    ]
    output = subprocess.check_output(args, shell=False, encoding="ascii")
    assert expectedSVGOutput.splitlines() == output.splitlines()
