from setuptools import setup, find_packages
import os

setup(
    name="fluxdb",
    version="0.1.3",
    packages=find_packages(),
    install_requires=[
        "psutil>=5.9.0",  # Добавлена зависимость psutil
    ],
    author="lkardas",
    author_email="your.email@example.com",
    description="FluxDB: A lightweight, file-based NoSQL database for Python with binary storage, indexing, transactions, and a simple query language. Perfect for embedded systems, mobile apps, and prototyping.",
    long_description=open("README.md", encoding="utf-8").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/lkardas/fluxdb",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Embedded Systems",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    keywords="nosql database embedded file-based lightweight python mobile",
)
