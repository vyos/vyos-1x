# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.


# pylint: disable=too-few-public-methods

import json
from html import escape
from enum import Enum
from typing import List
from typing import Union
from typing import Dict
from typing import Self

from pydantic import BaseModel
from pydantic import StrictStr
from pydantic import field_validator
from pydantic import model_validator
from fastapi.responses import HTMLResponse


def error(code, msg):
    msg = escape(msg, quote=False)
    resp = {'success': False, 'error': msg, 'data': None}
    resp = json.dumps(resp)
    return HTMLResponse(resp, status_code=code)


def success(data):
    resp = {'success': True, 'data': data, 'error': None}
    resp = json.dumps(resp)
    return HTMLResponse(resp)


# Pydantic models for validation
# Pydantic will cast when possible, so use StrictStr validators added as
# needed for additional constraints
# json_schema_extra adds anotations to OpenAPI to add examples


class ApiModel(BaseModel):
    key: StrictStr


class BasePathModel(BaseModel):
    op: StrictStr
    path: List[StrictStr]

    @field_validator('path')
    @classmethod
    def check_non_empty(cls, path: str) -> str:
        if not len(path) > 0:
            raise ValueError('path must be non-empty')
        return path


class BaseConfigureModel(BasePathModel):
    value: StrictStr = None


class ConfigureModel(ApiModel, BaseConfigureModel):
    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'set | delete | comment',
                'path': ['config', 'mode', 'path'],
            }
        }


class ConfigureListModel(ApiModel):
    commands: List[BaseConfigureModel]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'commands': 'list of commands',
            }
        }


class BaseConfigSectionModel(BasePathModel):
    section: Dict


class ConfigSectionModel(ApiModel, BaseConfigSectionModel):
    pass


class ConfigSectionListModel(ApiModel):
    commands: List[BaseConfigSectionModel]


class BaseConfigSectionTreeModel(BaseModel):
    op: StrictStr
    mask: Dict
    config: Dict


class ConfigSectionTreeModel(ApiModel, BaseConfigSectionTreeModel):
    pass


class RetrieveModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]
    configFormat: StrictStr = None

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'returnValue | returnValues | exists | showConfig',
                'path': ['config', 'mode', 'path'],
                'configFormat': 'json (default) | json_ast | raw',
            }
        }


class ConfigFileModel(ApiModel):
    op: StrictStr
    file: StrictStr = None

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'save | load',
                'file': 'filename',
            }
        }


class ImageOp(str, Enum):
    add = 'add'
    delete = 'delete'
    show = 'show'
    set_default = 'set_default'


class ImageModel(ApiModel):
    op: ImageOp
    url: StrictStr = None
    name: StrictStr = None

    @model_validator(mode='after')
    def check_data(self) -> Self:
        if self.op == 'add':
            if not self.url:
                raise ValueError('Missing required field "url"')
        elif self.op in ['delete', 'set_default']:
            if not self.name:
                raise ValueError('Missing required field "name"')

        return self

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'add | delete | show | set_default',
                'url': 'imagelocation',
                'name': 'imagename',
            }
        }


class ImportPkiModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]
    passphrase: StrictStr = None

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'import_pki',
                'path': ['op', 'mode', 'path'],
                'passphrase': 'passphrase',
            }
        }


class ContainerImageModel(ApiModel):
    op: StrictStr
    name: StrictStr = None

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'add | delete | show',
                'name': 'imagename',
            }
        }


class GenerateModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'generate',
                'path': ['op', 'mode', 'path'],
            }
        }


class ShowModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'show',
                'path': ['op', 'mode', 'path'],
            }
        }


class RebootModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'reboot',
                'path': ['op', 'mode', 'path'],
            }
        }


class ResetModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'reset',
                'path': ['op', 'mode', 'path'],
            }
        }


class PoweroffModel(ApiModel):
    op: StrictStr
    path: List[StrictStr]

    class Config:
        json_schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'poweroff',
                'path': ['op', 'mode', 'path'],
            }
        }


class TracerouteModel(ApiModel):
    op: StrictStr
    host: StrictStr

    class Config:
        schema_extra = {
            'example': {
                'key': 'id_key',
                'op': 'traceroute',
                'host': 'host',
            }
        }


class Success(BaseModel):
    success: bool
    data: Union[str, bool, Dict]
    error: str


class Error(BaseModel):
    success: bool = False
    data: Union[str, bool, Dict]
    error: str


responses = {
    200: {'model': Success},
    400: {'model': Error},
    422: {'model': Error, 'description': 'Validation Error'},
    500: {'model': Error},
}
