from setuptools import setup, find_packages
from Cython.Build import cythonize
import os

setup(
    name="fluxdb",
    version="0.1.3",
    packages=find_packages(),
    ext_modules=cythonize(["fluxdb/core.pyx", "fluxdb/indexing.pyx"], language_level=3),
    install_requires=[],
    author="Your Name",
    author_email="your.email@example.com",
    description="A lightweight, binary-format database library for Python with JSON indexes",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",  # Исправляем путь
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/fluxdb",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
