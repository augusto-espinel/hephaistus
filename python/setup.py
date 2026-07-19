"""
Setup script for backwards compatibility with older pip versions.
Use pyproject.toml for modern installation.
"""

from setuptools import setup, find_packages

setup(
    name="hephaistus",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "kiutils>=1.0.0",
    ],
    extras_require={
        "simulation": ["skidl>=1.0.0"],
        "dev": ["pytest>=7.0.0", "black>=23.0.0", "mypy>=1.0.0"],
    },
)