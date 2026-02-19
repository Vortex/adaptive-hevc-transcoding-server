from pathlib import Path
import re

from setuptools import find_packages, setup


def _read_version() -> str:
    text = Path("adaptive_hevc_transcoding_server/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text) or re.search(r"__version__\s*=\s*'([^']+)'", text)
    if not match:
        raise RuntimeError("Unable to find __version__ in adaptive_hevc_transcoding_server/__init__.py")
    return match.group(1)


setup(
    name="adaptive-hevc-transcoding-server",
    version=_read_version(),
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ],
    entry_points={
        "console_scripts": [
            "adaptive-hevc-transcoding-server=adaptive_hevc_transcoding_server.cli:main",
            "ahc-transcoding-server=adaptive_hevc_transcoding_server.cli:main",
        ],
    },
    author="Vortex",
    description="Chunked HTTP transcoding worker for Adaptive HEVC Converter.",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)

