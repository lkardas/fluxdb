from setuptools import setup, find_packages
from Cython.Build import cythonize
import os

setup(
    name="fluxdb",
    version="0.1.3",
    packages=find_packages(),
    ext_modules=cythonize(["fluxdb/core.pyx", "fluxdb/indexing.pyx"], language_level=3),
    install_requires=[],
    author="lkardas",
    author_email="your.email@example.com",
    description="FluxDB is a lightweight file-based NoSQL database in Python, featuring collections, indexing, transactions, binary data storage, and a simple query language. It’s ideal for projects that don’t require an external DBMS and where an embedded solution is preferred.",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",  
    long_description_content_type="text/markdown",
    url="https://github.com/lkardas/fluxdb",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
