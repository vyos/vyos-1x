# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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


# pylint: disable=line-too-long,raise-missing-from,invalid-name
# pylint: disable=wildcard-import,unused-wildcard-import
# pylint: disable=broad-exception-caught

import json
import copy
import logging
import traceback
from threading import Lock
from typing import Union
from typing import Callable
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi import HTTPException
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi.routing import APIRoute
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import FormData
from starlette.formparsers import FormParser
from starlette.formparsers import MultiPartParser
from starlette.formparsers import MultiPartException
from multipart.multipart import parse_options_header

from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.configdiff import get_config_diff
from vyos.configsession import ConfigSessionError

from ..session import SessionState
from .models import success
from .models import error
from .models import responses
from .models import ApiModel
from .models import ConfigureModel
from .models import ConfirmModel
from .models import ConfigureListModel
from .models import ConfigSectionModel
from .models import ConfigSectionListModel
from .models import ConfigSectionTreeModel
from .models import BaseConfigSectionTreeModel
from .models import BaseConfigureModel
from .models import BaseConfigSectionModel
from .models import RetrieveModel
from .models import ConfigFileModel
from .models import ImageModel
from .models import ContainerImageModel
from .models import GenerateModel
from .models import ShowModel
from .models import RebootModel
from .models import ResetModel
from .models import RenewModel
from .models import ImportPkiModel
from .models import PoweroffModel
from .models import TracerouteModel


if TYPE_CHECKING:
    from fastapi import FastAPI


LOG = logging.getLogger('http_api.routers')

lock = Lock()


def check_auth(key_list, key):
    key_id = None
    for k in key_list:
        if k['key'] == key:
            key_id = k['id']
    return key_id


def auth_required(data: ApiModel):
    session = SessionState()
    key = data.key
    api_keys = session.keys
    key_id = check_auth(api_keys, key)
    if not key_id:
        raise HTTPException(status_code=401, detail='Valid API key is required')
    session.id = key_id


# override Request and APIRoute classes in order to convert form request to json;
# do all explicit validation here, for backwards compatability of error messages;
# the explicit validation may be dropped, if desired, in favor of native
# validation by FastAPI/Pydantic, as is used for application/json requests
class MultipartRequest(Request):
    """Override Request class to convert form request to json"""

    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-branches,too-many-statements

    _form_err = ()

    @property
    def form_err(self):
        return self._form_err

    @form_err.setter
    def form_err(self, val):
        if not self._form_err:
            self._form_err = val

    @property
    def orig_headers(self):
        self._orig_headers = super().headers
        return self._orig_headers

    @property
    def headers(self):
        self._headers = super().headers.mutablecopy()
        self._headers['content-type'] = 'application/json'
        return self._headers

    async def _get_form(
        self, *, max_files: int | float = 1000, max_fields: int | float = 1000
    ) -> FormData:
        if self._form is None:
            assert (
                parse_options_header is not None
            ), 'The `python-multipart` library must be installed to use form parsing.'
            content_type_header = self.orig_headers.get('Content-Type')
            content_type: bytes
            content_type, _ = parse_options_header(content_type_header)
            if content_type == b'multipart/form-data':
                try:
                    multipart_parser = MultiPartParser(
                        self.orig_headers,
                        self.stream(),
                        max_files=max_files,
                        max_fields=max_fields,
                    )
                    self._form = await multipart_parser.parse()
                except MultiPartException as exc:
                    if 'app' in self.scope:
                        raise HTTPException(status_code=400, detail=exc.message)
                    raise exc
            elif content_type == b'application/x-www-form-urlencoded':
                form_parser = FormParser(self.orig_headers, self.stream())
                self._form = await form_parser.parse()
            else:
                self._form = FormData()
        return self._form

    async def body(self) -> bytes:
        if not hasattr(self, '_body'):
            forms = {}
            merge = {}
            body = await super().body()
            self._body = body

            form_data = await self.form()
            if form_data:
                endpoint = self.url.path
                LOG.debug('processing form data')
                for k, v in form_data.multi_items():
                    forms[k] = v

                if 'data' not in forms:
                    self.form_err = (422, 'Non-empty data field is required')
                    return self._body
                try:
                    tmp = json.loads(forms['data'])
                except json.JSONDecodeError as e:
                    self.form_err = (400, f'Failed to parse JSON: {e}')
                    return self._body
                if isinstance(tmp, list):
                    merge['commands'] = tmp
                else:
                    merge = tmp

                if 'commands' in merge:
                    cmds = merge['commands']
                else:
                    cmds = copy.deepcopy(merge)
                    cmds = [cmds]

                for c in cmds:
                    if not isinstance(c, dict):
                        self.form_err = (
                            400,
                            f"Malformed command '{c}': any command must be JSON of dict",
                        )
                        return self._body
                    if 'op' not in c:
                        self.form_err = (
                            400,
                            f"Malformed command '{c}': missing 'op' field",
                        )
                    if endpoint not in (
                        '/config-file',
                        '/container-image',
                        '/image',
                        '/configure-section',
                        '/traceroute',
                    ):
                        if 'path' not in c:
                            self.form_err = (
                                400,
                                f"Malformed command '{c}': missing 'path' field",
                            )
                        elif not isinstance(c['path'], list):
                            self.form_err = (
                                400,
                                f"Malformed command '{c}': 'path' field must be a list",
                            )
                        elif not all(isinstance(el, str) for el in c['path']):
                            self.form_err = (
                                400,
                                f"Malformed command '{0}': 'path' field must be a list of strings",
                            )
                    if endpoint in ('/configure'):
                        if not c['path']:
                            self.form_err = (
                                400,
                                f"Malformed command '{c}': 'path' list must be non-empty",
                            )
                        if 'value' in c and not isinstance(c['value'], str):
                            self.form_err = (
                                400,
                                f"Malformed command '{c}': 'value' field must be a string",
                            )
                    if endpoint in ('/configure-section'):
                        if 'section' not in c and 'config' not in c:
                            self.form_err = (
                                400,
                                f"Malformed command '{c}': missing 'section' or 'config' field",
                            )

                if 'key' not in forms and 'key' not in merge:
                    self.form_err = (401, 'Valid API key is required')
                if 'key' in forms and 'key' not in merge:
                    merge['key'] = forms['key']

                new_body = json.dumps(merge)
                new_body = new_body.encode()
                self._body = new_body

        return self._body


class MultipartRoute(APIRoute):
    """Override APIRoute class to convert form request to json"""

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = MultipartRequest(request.scope, request.receive)
            try:
                response: Response = await original_route_handler(request)
            except HTTPException as e:
                return error(e.status_code, e.detail)
            except Exception as e:
                form_err = request.form_err
                if form_err:
                    return error(*form_err)
                raise e

            return response

        return custom_route_handler


router = APIRouter(
    route_class=MultipartRoute,
    responses={**responses},
    dependencies=[Depends(auth_required)],
)


self_ref_msg = 'Requested HTTP API server configuration change; commit will be called in the background'


def call_commit(s: SessionState):
    try:
        s.session.commit()
    except ConfigSessionError as e:
        s.session.discard()
        if s.debug:
            LOG.warning(f'ConfigSessionError:\n {traceback.format_exc()}')
        else:
            LOG.warning(f'ConfigSessionError: {e}')


def call_commit_confirm(s: SessionState):
    env = s.session.get_session_env()
    env['IN_COMMIT_CONFIRM'] = 't'
    try:
        s.session.commit()
        s.session.commit_confirm(minutes=s.confirm_time)
    except ConfigSessionError as e:
        s.session.discard()
        if s.debug:
            LOG.warning(f'ConfigSessionError:\n {traceback.format_exc()}')
        else:
            LOG.warning(f'ConfigSessionError: {e}')
    finally:
        del env['IN_COMMIT_CONFIRM']


def run_commit(s: SessionState):
    try:
        out = s.session.commit()
        return out, None
    except Exception as e:
        return None, e


def run_commit_confirm(s: SessionState):
    env = s.session.get_session_env()
    env['IN_COMMIT_CONFIRM'] = 't'
    try:
        out_c = s.session.commit()
        out_cc = s.session.commit_confirm(minutes=s.confirm_time)
        out = out_c + '\n' + out_cc
        return out, None
    except Exception as e:
        return None, e
    finally:
        del env['IN_COMMIT_CONFIRM']


async def _configure_op(
    data: Union[
        ConfirmModel,
        ConfigureModel,
        ConfigureListModel,
        ConfigSectionModel,
        ConfigSectionListModel,
        ConfigSectionTreeModel,
    ],
    _request: Request,
    background_tasks: BackgroundTasks,
):
    # pylint: disable=too-many-branches,too-many-locals,too-many-nested-blocks,too-many-statements
    # pylint: disable=consider-using-with

    state = SessionState()
    session = state.session
    env = session.get_session_env()

    # A non-zero confirm_time will start commit-confirm timer on commit
    confirm_time = 0
    if isinstance(data, (ConfigureModel, ConfigureListModel, ConfigFileModel)):
        confirm_time = data.confirm_time

    # Allow users to pass just one command
    if not isinstance(data, (ConfigureListModel, ConfigSectionListModel)):
        data = [data]
    else:
        data = data.commands

    # We don't want multiple people/apps to be able to commit at once,
    # or modify the shared session while someone else is doing the same,
    # so the lock is really global
    lock.acquire()

    config = Config(session_env=env)

    status = 200
    msg = None
    error_msg = None
    try:
        for c in data:
            op = c.op
            if not isinstance(c, (ConfirmModel, BaseConfigSectionTreeModel)):
                path = c.path

            if isinstance(c, ConfirmModel):
                if op == 'confirm':
                    msg = session.confirm()
                else:
                    raise ConfigSessionError(f"'{op}' is not a valid operation")

            elif isinstance(c, BaseConfigureModel):
                if c.value:
                    value = c.value
                else:
                    value = ''
                # For vyos.configsession calls that have no separate value arguments,
                # and for type checking too
                cfg_path = ' '.join(path + [value]).strip()

            elif isinstance(c, BaseConfigSectionModel):
                section = c.section

            elif isinstance(c, BaseConfigSectionTreeModel):
                mask = c.mask
                config = c.config

            if isinstance(c, BaseConfigureModel):
                if op == 'set':
                    session.set(path, value=value)
                elif op == 'delete':
                    if state.strict and not config.exists(cfg_path):
                        raise ConfigSessionError(
                            f'Cannot delete [{cfg_path}]: path/value does not exist'
                        )
                    session.delete(path, value=value)
                elif op == 'comment':
                    session.comment(path, value=value)
                else:
                    raise ConfigSessionError(f"'{op}' is not a valid operation")

            elif isinstance(c, BaseConfigSectionModel):
                if op == 'set':
                    session.set_section(path, section)
                elif op == 'load':
                    session.load_section(path, section)
                else:
                    raise ConfigSessionError(f"'{op}' is not a valid operation")

            elif isinstance(c, BaseConfigSectionTreeModel):
                if op == 'set':
                    session.set_section_tree(config)
                elif op == 'load':
                    session.load_section_tree(mask, config)
                else:
                    raise ConfigSessionError(f"'{op}' is not a valid operation")
        # end for

        config = Config(session_env=env)
        d = get_config_diff(config)

        state.confirm_time = confirm_time if confirm_time else 0

        if not d.is_node_changed(['service', 'https']):
            if confirm_time:
                out, err = await run_in_threadpool(run_commit_confirm, state)
                if err:
                    raise err
                msg = msg + out if msg else out
            else:
                out, err = await run_in_threadpool(run_commit, state)
                if err:
                    raise err
                msg = msg + out if msg else out
        else:
            if confirm_time:
                background_tasks.add_task(call_commit_confirm, state)
            else:
                background_tasks.add_task(call_commit, state)
            out = self_ref_msg
            msg = msg + out if msg else out

        LOG.info(f"Configuration modified via HTTP API using key '{state.id}'")
    except ConfigSessionError as e:
        session.discard()
        status = 400
        if state.debug:
            LOG.critical(f'ConfigSessionError:\n {traceback.format_exc()}')
        error_msg = str(e)
    except Exception:
        session.discard()
        LOG.critical(traceback.format_exc())
        status = 500

        # Don't give the details away to the outer world
        error_msg = 'An internal error occured. Check the logs for details.'
    finally:
        if 'IN_COMMIT_CONFIRM' in env:
            del env['IN_COMMIT_CONFIRM']
        lock.release()

    if status != 200:
        return error(status, error_msg)

    return success(msg)


def create_path_import_pki_no_prompt(path):
    correct_paths = ['ca', 'certificate', 'key-pair']
    if path[1] not in correct_paths:
        return False
    path[3] = '--key-filename'
    path.insert(2, '--name')
    return ['--pki-type'] + path[1:]


@router.post('/configure')
async def configure_op(
    data: Union[ConfigureModel, ConfigureListModel, ConfirmModel],
    request: Request,
    background_tasks: BackgroundTasks,
):
    out = await _configure_op(data, request, background_tasks)

    return out


@router.post('/configure-section')
async def configure_section_op(
    data: Union[ConfigSectionModel, ConfigSectionListModel, ConfigSectionTreeModel],
    request: Request,
    background_tasks: BackgroundTasks,
):
    out = await _configure_op(data, request, background_tasks)

    return out


@router.post('/retrieve')
async def retrieve_op(data: RetrieveModel):
    state = SessionState()
    session = state.session
    env = session.get_session_env()
    config = Config(session_env=env)

    op = data.op
    path = ' '.join(data.path)

    try:
        if op == 'returnValue':
            res = config.return_value(path)
        elif op == 'returnValues':
            res = config.return_values(path)
        elif op == 'exists':
            res = config.exists(path)
        elif op == 'showConfig':
            config_format = 'json'
            if data.configFormat:
                config_format = data.configFormat

            res = session.show_config(path=data.path)
            if config_format == 'json':
                config_tree = ConfigTree(res)
                res = json.loads(config_tree.to_json())
            elif config_format == 'json_ast':
                config_tree = ConfigTree(res)
                res = json.loads(config_tree.to_json_ast())
            elif config_format == 'raw':
                pass
            else:
                return error(400, f"'{config_format}' is not a valid config format")
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/config-file')
async def config_file_op(data: ConfigFileModel, background_tasks: BackgroundTasks):
    state = SessionState()
    session = state.session
    env = session.get_session_env()
    op = data.op
    msg = None

    # A non-zero confirm_time will start commit-confirm timer on commit
    confirm_time = data.confirm_time

    lock.acquire()

    try:
        if op == 'save':
            if data.file:
                path = data.file
            else:
                path = '/config/config.boot'
            msg = session.save_config(path)
        elif op in ('load', 'merge'):
            if data.file:
                path = data.file
            elif data.string:
                path = '/tmp/config.file'
                with open(path, 'w') as f:
                    f.write(data.string)
            else:
                return error(400, 'Missing required field "file | string"')

            match op:
                case 'load':
                    session.migrate_and_load_config(path)
                case 'merge':
                    session.merge_config(path, destructive=data.destructive)

            config = Config(session_env=env)
            d = get_config_diff(config)

            state.confirm_time = confirm_time if confirm_time else 0

            if not d.is_node_changed(['service', 'https']):
                if confirm_time:
                    out, err = await run_in_threadpool(run_commit_confirm, state)
                    if err:
                        raise err
                    msg = msg + out if msg else out
                else:
                    out, err = await run_in_threadpool(run_commit, state)
                    if err:
                        raise err
                    msg = msg + out if msg else out
            else:
                if confirm_time:
                    background_tasks.add_task(call_commit_confirm, state)
                else:
                    background_tasks.add_task(call_commit, state)
                out = self_ref_msg
                msg = msg + out if msg else out

        elif op == 'confirm':
            msg = session.confirm()
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')
    finally:
        if 'IN_COMMIT_CONFIRM' in env:
            del env['IN_COMMIT_CONFIRM']
        lock.release()

    return success(msg)


@router.post('/image')
def image_op(data: ImageModel):
    state = SessionState()
    session = state.session

    op = data.op

    try:
        if op == 'add':
            res = session.install_image(data.url)
        elif op == 'delete':
            res = session.remove_image(data.name)
        elif op == 'show':
            res = session.show(['system', 'image'])
        elif op == 'set_default':
            res = session.set_default_image(data.name)
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/container-image')
def container_image_op(data: ContainerImageModel):
    state = SessionState()
    session = state.session

    op = data.op

    try:
        if op == 'add':
            if data.name:
                name = data.name
            else:
                return error(400, 'Missing required field "name"')
            res = session.add_container_image(name)
        elif op == 'delete':
            if data.name:
                name = data.name
            else:
                return error(400, 'Missing required field "name"')
            res = session.delete_container_image(name)
        elif op == 'show':
            res = session.show_container_image()
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/generate')
def generate_op(data: GenerateModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'generate':
            res = session.generate(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/show')
def show_op(data: ShowModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'show':
            res = session.show(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/reboot')
def reboot_op(data: RebootModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'reboot':
            res = session.reboot(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)

@router.post('/renew')
def renew_op(data: RenewModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'renew':
            res = session.renew(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)

@router.post('/reset')
def reset_op(data: ResetModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'reset':
            res = session.reset(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/import-pki')
def import_pki(data: ImportPkiModel):
    # pylint: disable=consider-using-with

    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    lock.acquire()

    try:
        if op == 'import-pki':
            # need to get rid or interactive mode for private key
            if len(path) == 5 and path[3] in ['key-file', 'private-key']:
                path_no_prompt = create_path_import_pki_no_prompt(path)
                if not path_no_prompt:
                    return error(400, f"Invalid command: {' '.join(path)}")
                if data.passphrase:
                    path_no_prompt += ['--passphrase', data.passphrase]
                res = session.import_pki_no_prompt(path_no_prompt)
            else:
                res = session.import_pki(path)
            if not res[0].isdigit():
                return error(400, res)
            # commit changes
            session.commit()
            res = res.split('. ')[0]
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')
    finally:
        lock.release()

    return success(res)


@router.post('/poweroff')
def poweroff_op(data: PoweroffModel):
    state = SessionState()
    session = state.session

    op = data.op
    path = data.path

    try:
        if op == 'poweroff':
            res = session.poweroff(path)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occured. Check the logs for details.')

    return success(res)


@router.post('/traceroute')
def traceroute_op(data: TracerouteModel):
    state = SessionState()
    session = state.session

    op = data.op
    host = data.host

    try:
        if op == 'traceroute':
            res = session.traceroute(host)
        else:
            return error(400, f"'{op}' is not a valid operation")
    except ConfigSessionError as e:
        return error(400, str(e))
    except Exception:
        LOG.critical(traceback.format_exc())
        return error(500, 'An internal error occurred. Check the logs for details.')

    return success(res)


def rest_init(app: 'FastAPI'):
    if all(r in app.routes for r in router.routes):
        return
    app.include_router(router)


def rest_clear(app: 'FastAPI'):
    for r in router.routes:
        if r in app.routes:
            app.routes.remove(r)
