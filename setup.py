# Copyright 2021 Black Foundry. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from setuptools import setup, find_packages


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="blackrenderer",
    use_scm_version={"write_to": "Lib/blackrenderer/_version.py"},
    description=(
        "A Python-based renderer for OpenType COLRv1 fonts, with multiple backends."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Black Foundry, Just van Rossum, Samuel Hornus",
    author_email="justvanrossum@gmail.com",
    license="Apache Software License 2.0",
    url="https://github.com/BlackFoundryCom/black-renderer",
    python_requires=">=3.10",
    package_dir={"": "Lib"},
    packages=find_packages("Lib"),
    install_requires=[
        "fonttools >= 4.62.1",
        "uharfbuzz >= 0.53.2",
    ],
    extras_require={
        "skia": ["skia-python", "numpy"],
        "cairo": ["pycairo"],
        "cg": ["pyobjc; sys_platform == 'darwin'"],
    },
    setup_requires=["setuptools_scm"],
    entry_points={
        "console_scripts": [
            "blackrenderer=blackrenderer.__main__:main",
        ],
    },
)
