import os
from setuptools import setup

def packages(directory):
    return [
        _[0].replace('/','.')
        for _ in os.walk(directory)
        if os.path.isfile(os.path.join(_[0], '__init__.py'))
    ]

setup(
    name = "vyos",
    version = "1.3.0",
    author = "VyOS maintainers and contributors",
    author_email = "maintainers@vyos.net",
    description = ("VyOS configuration libraries."),
    license = "LGPLv2+",
    keywords = "vyos",
    url = "http://www.vyos.io",
    packages = packages('vyos'),
    long_description="VyOS configuration libraries",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
    ],
    entry_points={
        "console_scripts": [
            "config-mgmt = vyos.config_mgmt:run",
        ],
    },
)
