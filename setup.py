from setuptools import setup, find_packages
import os

setup(
    name="fluxdb",
    version="0.1.1",  
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "psutil>=5.9.0",
        "flask>=2.0.0",
        "flask-admin>=1.6.0",
    ],
    author="lkardas",
    description="A lightweight, file-based NoSQL database for Python (not affiliated with InfluxDB)",
    long_description=open("readmee.md", encoding="utf-8").read() if os.path.exists("readmee.md") else "",
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
    keywords="nosql database embedded file-based lightweight python",
    package_data={
        "fluxdb": [
            "templates/admin/*.html",
            "static/css/*.css",
            "LICENSE",
            "readmee.md",
            "README.md",
        ],
    },
)
