#!/usr/bin/env python3

from distutils.core import setup

setup(
    name="bkeep",
    version="0.0.1",
    description="A python script of bookkeeping",
    long_description=open("README.md", "rb").read().decode("utf-8"),
    author="ugos",
    url="https://github.com/python-bkeep/bkeep",
    packages=["bkeep"],
    scripts=["bin/bkeep"]
)
