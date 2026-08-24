"""Setup script for GameForge (legacy setuptools entry point).

Modern installs should use ``pip install -e .`` which reads
``pyproject.toml``; this file remains for tooling that still invokes
``python setup.py`` directly.
"""

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent
LONG_DESCRIPTION = (HERE / "README.md").read_text(encoding="utf-8")

setup(
    name="gameforge",
    version="0.1.0",
    description="A modular 2D game engine written in Python",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="GameForge Team",
    author_email="team@gameforge.dev",
    url="https://github.com/gameforge/gameforge",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(include=["src", "src.*"]),
    install_requires=[
        "pygame-ce>=2.5",
        "numpy>=1.26",
    ],
    extras_require={
        "scripting": ["lupa>=2.0"],
        "dev": [
            "pytest>=8.0",
            "pytest-cov>=5.0",
            "mypy>=1.10",
            "black>=24.4",
            "flake8>=7.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: pygame",
    ],
    keywords="game engine 2d ecs physics renderer gamedev",
)
