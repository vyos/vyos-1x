import os
import sys
import subprocess
from setuptools import setup
from setuptools.command.build_py import build_py

sys.path.append('./vyos')
from defaults import directories

def packages(directory):
    return [
        _[0].replace('/','.')
        for _ in os.walk(directory)
        if os.path.isfile(os.path.join(_[0], '__init__.py'))
    ]


class GenerateProto(build_py):
    ver = os.environ.get('OCAML_VERSION')
    if ver:
        proto_path = f'/opt/opam/{ver}/share/vyconf'
    else:
        proto_path = directories['proto_path']

    def run(self):
        # find all .proto files in vyconf proto_path
        proto_files = []
        for _, _, files in os.walk(self.proto_path):
            for file in files:
                if file.endswith('.proto'):
                    proto_files.append(file)

        # compile each .proto file to Python
        for proto_file in proto_files:
            subprocess.check_call(
                [
                    'protoc',
                    '--python_out=vyos/proto',
                    f'--proto_path={self.proto_path}/',
                    proto_file,
                ]
            )

        build_py.run(self)

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
    cmdclass={
        'build_py': GenerateProto,
    },
)
