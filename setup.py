"""setup.py

This is a setup script for the eulercopilot package.
"""

from setuptools import find_packages, setup

setup(
    name="eulercopilot",
    version="0.9.6",
    description="智能 Shell 命令行工具",
    author="openEuler",
    author_email="contact@openeuler.org",
    url="https://gitee.com/openeuler/euler-copilot-shell",
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
            "eulercopilot=main:main",
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
