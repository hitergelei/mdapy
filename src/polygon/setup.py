from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension

ext_modules = [
    Pybind11Extension(
        "poly",
        ["polygon.cpp", "wrap.cpp", "../../thirdparty/voro++/voro++.cc"],
        language="c++",
        include_dirs=["../../thirdparty/voro++"],
    ),
]

setup(
    name="mdapy",
    version="0.0.1",
    ext_modules=ext_modules,
)