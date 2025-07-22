#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
import argparse
import os

from google.protobuf.descriptor_pb2 import FileDescriptorSet  # pylint: disable=no-name-in-module
from google.protobuf.descriptor_pb2 import FieldDescriptorProto  # pylint: disable=no-name-in-module
from humps import decamelize

HEADER = """\
from enum import IntEnum
from dataclasses import dataclass
from dataclasses import field
"""


def normalize(s: str) -> str:
    """Decamelize and avoid syntactic collision"""
    t = decamelize(s)
    return t + '_' if t in ['from'] else t


def generate_dataclass(descriptor_proto):
    class_name = descriptor_proto.name
    fields = []
    for field_p in descriptor_proto.field:
        field_name = field_p.name
        field_type, field_default = get_type(field_p.type, field_p.type_name)
        match field_p.label:
            case FieldDescriptorProto.LABEL_REPEATED:
                field_type = f'list[{field_type}] = field(default_factory=list)'
            case FieldDescriptorProto.LABEL_OPTIONAL:
                field_type = f'{field_type} = None'
            case _:
                field_type = f'{field_type} = {field_default}'

        fields.append(f'    {field_name}: {field_type}')

    code = f"""
@dataclass
class {class_name}:
{chr(10).join(fields) if fields else '    pass'}
"""

    return code


def generate_request(descriptor_proto):
    class_name = descriptor_proto.name
    fields = []
    f_vars = []
    for field_p in descriptor_proto.field:
        field_name = field_p.name
        field_type, field_default = get_type(field_p.type, field_p.type_name)
        match field_p.label:
            case FieldDescriptorProto.LABEL_REPEATED:
                field_type = f'list[{field_type}] = []'
            case FieldDescriptorProto.LABEL_OPTIONAL:
                field_type = f'{field_type} = None'
            case _:
                field_type = f'{field_type} = {field_default}'

        fields.append(f'{normalize(field_name)}: {field_type}')
        f_vars.append(f'{normalize(field_name)}')

    fields.insert(0, 'token: str = None')

    code = f"""
def set_request_{decamelize(class_name)}({', '.join(fields)}):
    reqi = {class_name} ({', '.join(f_vars)})
    req = Request({decamelize(class_name)}=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env
"""

    return code


def generate_nested_dataclass(descriptor_proto):
    out = ''
    for nested_p in descriptor_proto.nested_type:
        out = out + generate_dataclass(nested_p)

    return out


def generate_nested_request(descriptor_proto):
    out = ''
    for nested_p in descriptor_proto.nested_type:
        out = out + generate_request(nested_p)

    return out


def generate_enum_dataclass(descriptor_proto):
    code = ''
    for enum_p in descriptor_proto.enum_type:
        enums = []
        enum_name = enum_p.name
        for enum_val in enum_p.value:
            enums.append(f'    {enum_val.name} = {enum_val.number}')

        code += f"""
class {enum_name}(IntEnum):
{chr(10).join(enums)}
"""

    return code


def get_type(field_type, type_name):
    res = 'Any', None
    match field_type:
        case FieldDescriptorProto.TYPE_STRING:
            res = 'str', '""'
        case FieldDescriptorProto.TYPE_INT32 | FieldDescriptorProto.TYPE_INT64:
            res = 'int', 0
        case FieldDescriptorProto.TYPE_FLOAT | FieldDescriptorProto.TYPE_DOUBLE:
            res = 'float', 0.0
        case FieldDescriptorProto.TYPE_BOOL:
            res = 'bool', False
        case FieldDescriptorProto.TYPE_MESSAGE | FieldDescriptorProto.TYPE_ENUM:
            res = type_name.split('.')[-1], None
        case _:
            pass

    return res


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('descriptor_file', help='protobuf .desc file')
    parser.add_argument('--out-dir', help='directory to write generated file')
    args = parser.parse_args()
    desc_file = args.descriptor_file
    out_dir = args.out_dir

    with open(desc_file, 'rb') as f:
        descriptor_set_data = f.read()

    descriptor_set = FileDescriptorSet()
    descriptor_set.ParseFromString(descriptor_set_data)

    for file_proto in descriptor_set.file:
        f = f'{file_proto.name.replace(".", "_")}.py'
        f = os.path.join(out_dir, f)
        dataclass_code = ''
        nested_code = ''
        enum_code = ''
        request_code = ''
        with open(f, 'w') as f:
            enum_code += generate_enum_dataclass(file_proto)
            for message_proto in file_proto.message_type:
                dataclass_code += generate_dataclass(message_proto)
                nested_code += generate_nested_dataclass(message_proto)
                enum_code += generate_enum_dataclass(message_proto)
                request_code += generate_nested_request(message_proto)

            f.write(HEADER)
            f.write(enum_code)
            f.write(nested_code)
            f.write(dataclass_code)
            f.write(request_code)
