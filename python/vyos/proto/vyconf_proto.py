from enum import IntEnum
from dataclasses import dataclass
from dataclasses import field

class Errnum(IntEnum):
    SUCCESS = 0
    FAIL = 1
    INVALID_PATH = 2
    INVALID_VALUE = 3
    COMMIT_IN_PROGRESS = 4
    CONFIGURATION_LOCKED = 5
    INTERNAL_ERROR = 6
    PERMISSION_DENIED = 7
    PATH_ALREADY_EXISTS = 8
    UNCOMMITED_CHANGES = 9

class ConfigFormat(IntEnum):
    CURLY = 0
    JSON = 1

class OutputFormat(IntEnum):
    OutPlain = 0
    OutJSON = 1

@dataclass
class Prompt:
    pass

@dataclass
class SetupSession:
    client_pid: int = 0
    client_application: str = None
    on_behalf_of: int = None
    client_user: str = None
    client_sudo_user: str = None

@dataclass
class SessionOfPid:
    client_pid: int = 0

@dataclass
class SessionExists:
    dummy: int = None

@dataclass
class GetConfig:
    dummy: int = None

@dataclass
class Teardown:
    on_behalf_of: int = None

@dataclass
class Validate:
    Path: list[str] = field(default_factory=list)
    output_format: OutputFormat = None

@dataclass
class Set:
    path: list[str] = field(default_factory=list)

@dataclass
class Delete:
    path: list[str] = field(default_factory=list)

@dataclass
class AuxSet:
    path: list[str] = field(default_factory=list)
    script_name: str = ""
    tag_value: str = None

@dataclass
class AuxDelete:
    path: list[str] = field(default_factory=list)
    script_name: str = ""
    tag_value: str = None

@dataclass
class Discard:
    dummy: int = None

@dataclass
class SessionChanged:
    dummy: int = None

@dataclass
class Rename:
    edit_level: list[str] = field(default_factory=list)
    source: str = ""
    destination: str = ""

@dataclass
class Copy:
    edit_level: list[str] = field(default_factory=list)
    source: str = ""
    destination: str = ""

@dataclass
class Comment:
    path: list[str] = field(default_factory=list)
    comment: str = ""

@dataclass
class Commit:
    confirm: bool = None
    confirm_timeout: int = None
    comment: str = None
    dry_run: bool = None

@dataclass
class Rollback:
    revision: int = 0

@dataclass
class Load:
    location: str = ""
    cached: bool = False
    format: ConfigFormat = None

@dataclass
class Merge:
    location: str = ""
    destructive: bool = False
    format: ConfigFormat = None

@dataclass
class Save:
    location: str = ""
    format: ConfigFormat = None

@dataclass
class ShowConfig:
    path: list[str] = field(default_factory=list)
    format: ConfigFormat = None

@dataclass
class Exists:
    path: list[str] = field(default_factory=list)

@dataclass
class GetValue:
    path: list[str] = field(default_factory=list)
    output_format: OutputFormat = None

@dataclass
class GetValues:
    path: list[str] = field(default_factory=list)
    output_format: OutputFormat = None

@dataclass
class ListChildren:
    path: list[str] = field(default_factory=list)
    output_format: OutputFormat = None

@dataclass
class RunOpMode:
    path: list[str] = field(default_factory=list)
    output_format: OutputFormat = None

@dataclass
class Confirm:
    pass

@dataclass
class EnterConfigurationMode:
    exclusive: bool = False
    override_exclusive: bool = False

@dataclass
class ExitConfigurationMode:
    pass

@dataclass
class ReloadReftree:
    on_behalf_of: int = None

@dataclass
class ShowSessions:
    exclude_self: bool = False
    exclude_other: bool = False

@dataclass
class SetEditLevel:
    path: list[str] = field(default_factory=list)

@dataclass
class SetEditLevelUp:
    dummy: int = None

@dataclass
class ResetEditLevel:
    dummy: int = None

@dataclass
class GetEditLevel:
    dummy: int = None

@dataclass
class EditLevelRoot:
    dummy: int = None

@dataclass
class ConfigUnsaved:
    file: str = None

@dataclass
class ReferencePathExists:
    path: list[str] = field(default_factory=list)

@dataclass
class GetPathType:
    path: list[str] = field(default_factory=list)
    legacy_format: bool = False

@dataclass
class GetCompletionEnv:
    path: list[str] = field(default_factory=list)
    legacy_format: bool = False

@dataclass
class Request:
    prompt: Prompt = None
    setup_session: SetupSession = None
    set: Set = None
    delete: Delete = None
    rename: Rename = None
    copy: Copy = None
    comment: Comment = None
    commit: Commit = None
    rollback: Rollback = None
    merge: Merge = None
    save: Save = None
    show_config: ShowConfig = None
    exists: Exists = None
    get_value: GetValue = None
    get_values: GetValues = None
    list_children: ListChildren = None
    run_op_mode: RunOpMode = None
    confirm: Confirm = None
    enter_configuration_mode: EnterConfigurationMode = None
    exit_configuration_mode: ExitConfigurationMode = None
    validate: Validate = None
    teardown: Teardown = None
    reload_reftree: ReloadReftree = None
    load: Load = None
    discard: Discard = None
    session_changed: SessionChanged = None
    session_of_pid: SessionOfPid = None
    session_exists: SessionExists = None
    get_config: GetConfig = None
    aux_set: AuxSet = None
    aux_delete: AuxDelete = None
    show_sessions: ShowSessions = None
    set_edit_level: SetEditLevel = None
    set_edit_level_up: SetEditLevelUp = None
    reset_edit_level: ResetEditLevel = None
    get_edit_level: GetEditLevel = None
    edit_level_root: EditLevelRoot = None
    config_unsaved: ConfigUnsaved = None
    reference_path_exists: ReferencePathExists = None
    get_path_type: GetPathType = None
    get_completion_env: GetCompletionEnv = None

@dataclass
class RequestEnvelope:
    token: str = None
    request: Request = None

@dataclass
class Response:
    status: Errnum = None
    output: str = None
    error: str = None
    warning: str = None

def set_request_prompt(token: str = None):
    reqi = Prompt ()
    req = Request(prompt=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_setup_session(token: str = None, client_pid: int = 0, client_application: str = None, on_behalf_of: int = None, client_user: str = None, client_sudo_user: str = None):
    reqi = SetupSession (client_pid, client_application, on_behalf_of, client_user, client_sudo_user)
    req = Request(setup_session=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_session_of_pid(token: str = None, client_pid: int = 0):
    reqi = SessionOfPid (client_pid)
    req = Request(session_of_pid=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_session_exists(token: str = None, dummy: int = None):
    reqi = SessionExists (dummy)
    req = Request(session_exists=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_config(token: str = None, dummy: int = None):
    reqi = GetConfig (dummy)
    req = Request(get_config=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_teardown(token: str = None, on_behalf_of: int = None):
    reqi = Teardown (on_behalf_of)
    req = Request(teardown=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_validate(token: str = None, path: list[str] = [], output_format: OutputFormat = None):
    reqi = Validate (path, output_format)
    req = Request(validate=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_set(token: str = None, path: list[str] = []):
    reqi = Set (path)
    req = Request(set=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_delete(token: str = None, path: list[str] = []):
    reqi = Delete (path)
    req = Request(delete=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_aux_set(token: str = None, path: list[str] = [], script_name: str = "", tag_value: str = None):
    reqi = AuxSet (path, script_name, tag_value)
    req = Request(aux_set=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_aux_delete(token: str = None, path: list[str] = [], script_name: str = "", tag_value: str = None):
    reqi = AuxDelete (path, script_name, tag_value)
    req = Request(aux_delete=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_discard(token: str = None, dummy: int = None):
    reqi = Discard (dummy)
    req = Request(discard=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_session_changed(token: str = None, dummy: int = None):
    reqi = SessionChanged (dummy)
    req = Request(session_changed=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_rename(token: str = None, edit_level: list[str] = [], source: str = "", destination: str = ""):
    reqi = Rename (edit_level, source, destination)
    req = Request(rename=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_copy(token: str = None, edit_level: list[str] = [], source: str = "", destination: str = ""):
    reqi = Copy (edit_level, source, destination)
    req = Request(copy=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_comment(token: str = None, path: list[str] = [], comment: str = ""):
    reqi = Comment (path, comment)
    req = Request(comment=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_commit(token: str = None, confirm: bool = None, confirm_timeout: int = None, comment: str = None, dry_run: bool = None):
    reqi = Commit (confirm, confirm_timeout, comment, dry_run)
    req = Request(commit=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_rollback(token: str = None, revision: int = 0):
    reqi = Rollback (revision)
    req = Request(rollback=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_load(token: str = None, location: str = "", cached: bool = False, format: ConfigFormat = None):
    reqi = Load (location, cached, format)
    req = Request(load=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_merge(token: str = None, location: str = "", destructive: bool = False, format: ConfigFormat = None):
    reqi = Merge (location, destructive, format)
    req = Request(merge=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_save(token: str = None, location: str = "", format: ConfigFormat = None):
    reqi = Save (location, format)
    req = Request(save=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_show_config(token: str = None, path: list[str] = [], format: ConfigFormat = None):
    reqi = ShowConfig (path, format)
    req = Request(show_config=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_exists(token: str = None, path: list[str] = []):
    reqi = Exists (path)
    req = Request(exists=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_value(token: str = None, path: list[str] = [], output_format: OutputFormat = None):
    reqi = GetValue (path, output_format)
    req = Request(get_value=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_values(token: str = None, path: list[str] = [], output_format: OutputFormat = None):
    reqi = GetValues (path, output_format)
    req = Request(get_values=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_list_children(token: str = None, path: list[str] = [], output_format: OutputFormat = None):
    reqi = ListChildren (path, output_format)
    req = Request(list_children=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_run_op_mode(token: str = None, path: list[str] = [], output_format: OutputFormat = None):
    reqi = RunOpMode (path, output_format)
    req = Request(run_op_mode=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_confirm(token: str = None):
    reqi = Confirm ()
    req = Request(confirm=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_enter_configuration_mode(token: str = None, exclusive: bool = False, override_exclusive: bool = False):
    reqi = EnterConfigurationMode (exclusive, override_exclusive)
    req = Request(enter_configuration_mode=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_exit_configuration_mode(token: str = None):
    reqi = ExitConfigurationMode ()
    req = Request(exit_configuration_mode=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_reload_reftree(token: str = None, on_behalf_of: int = None):
    reqi = ReloadReftree (on_behalf_of)
    req = Request(reload_reftree=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_show_sessions(token: str = None, exclude_self: bool = False, exclude_other: bool = False):
    reqi = ShowSessions (exclude_self, exclude_other)
    req = Request(show_sessions=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_set_edit_level(token: str = None, path: list[str] = []):
    reqi = SetEditLevel (path)
    req = Request(set_edit_level=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_set_edit_level_up(token: str = None, dummy: int = None):
    reqi = SetEditLevelUp (dummy)
    req = Request(set_edit_level_up=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_reset_edit_level(token: str = None, dummy: int = None):
    reqi = ResetEditLevel (dummy)
    req = Request(reset_edit_level=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_edit_level(token: str = None, dummy: int = None):
    reqi = GetEditLevel (dummy)
    req = Request(get_edit_level=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_edit_level_root(token: str = None, dummy: int = None):
    reqi = EditLevelRoot (dummy)
    req = Request(edit_level_root=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_config_unsaved(token: str = None, file: str = None):
    reqi = ConfigUnsaved (file)
    req = Request(config_unsaved=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_reference_path_exists(token: str = None, path: list[str] = []):
    reqi = ReferencePathExists (path)
    req = Request(reference_path_exists=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_path_type(token: str = None, path: list[str] = [], legacy_format: bool = False):
    reqi = GetPathType (path, legacy_format)
    req = Request(get_path_type=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env

def set_request_get_completion_env(token: str = None, path: list[str] = [], legacy_format: bool = False):
    reqi = GetCompletionEnv (path, legacy_format)
    req = Request(get_completion_env=reqi)
    req_env = RequestEnvelope(token, req)
    return req_env
