import os
from setuptools import setup

setup(
    name = "vyos",
    version = "1.2.0",
    author = "VyOS maintainers and contributors",
    author_email = "maintainers@vyos.net",
    description = ("VyOS configuration libraries."),
    license = "MIT",
    keywords = "vyos",
    url = "http://www.vyos.io",
    packages=['vyos'],
    long_description="VyOS configuration libraries",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
    ],
)

