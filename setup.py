#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="eulercopilot-shell",
    version="0.1.0",
    description="智能 Shell 终端工具",
    author="openEuler",
    author_email="contact@openeuler.org",
    url="https://www.eulercopilot.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "openai>=1.61.0",
        "rich>=14.0.0",
        "textual>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "eulercopilot-shell=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MulanPSL-2.0 License",
    ],
    python_requires=">=3.9",
)
