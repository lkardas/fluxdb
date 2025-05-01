from setuptools import setup, find_packages
import os

setup(
    name="fluxdb",
    version="0.1.3",
    packages=find_packages(),
    ext_modules=cythonize(
        ["fluxdb/*.py"],  # Compile all .py files in fluxdb/
        exclude=["fluxdb/__init__.py"],
        language_level=3,
        compiler_directives={'language_level': 3}
    ),
    install_requires=[
        "Cython>=0.29.0",
    ],
    author="lkardas",
    author_email="your.email@example.com",
    description="FluxDB: A lightweight, file-based NoSQL database for Python with binary storage, indexing, transactions, and a simple query language. Perfect for embedded systems and prototyping.",
    long_description=open("README.md", encoding="utf-8").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/lkardas/fluxdb",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Embedded Systems",
    ],
    python_requires=">=3.6",
    keywords="nosql database embedded file-based lightweight python",
)
