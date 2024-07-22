# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os

from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import DEVNULL

def popen(command, flag='', shell=None, input=None, timeout=None, env=None,
          stdout=PIPE, stderr=PIPE, decode='utf-8'):
    """
    popen is a wrapper helper aound subprocess.Popen
    with it default setting it will return a tuple (out, err)
    out: the output of the program run
    err: the error code returned by the program

    it can be affected by the following flags:
    shell:   do not try to auto-detect if a shell is required
             for example if a pipe (|) or redirection (>, >>) is used
    input:   data to sent to the child process via STDIN
             the data should be bytes but string will be converted
    timeout: time after which the command will be considered to have failed
    env:     mapping that defines the environment variables for the new process
    stdout:  define how the output of the program should be handled
              - PIPE (default), sends stdout to the output
              - DEVNULL, discard the output
    stderr:  define how the output of the program should be handled
              - None (default), send/merge the data to/with stderr
              - PIPE, popen will append it to output
              - STDOUT, send the data to be merged with stdout
              - DEVNULL, discard the output
    decode:  specify the expected text encoding (utf-8, ascii, ...)
             the default is explicitely utf-8 which is python's own default

    usage:
    get both stdout and stderr: popen('command', stdout=PIPE, stderr=STDOUT)
    discard stdout and get stderr: popen('command', stdout=DEVNUL, stderr=PIPE)
    """

    # airbag must be left as an import in the function as otherwise we have a
    # a circual import dependency
    from vyos import debug
    from vyos import airbag

    # log if the flag is set, otherwise log if command is set
    if not debug.enabled(flag):
        flag = 'command'

    cmd_msg = f"cmd '{command}'"
    debug.message(cmd_msg, flag)

    use_shell = shell
    stdin = None
    if shell is None:
        use_shell = False
        if ' ' in command:
            use_shell = True
        if env:
            use_shell = True

    if input:
        stdin = PIPE
        input = input.encode() if type(input) is str else input

    p = Popen(command, stdin=stdin, stdout=stdout, stderr=stderr,
              env=env, shell=use_shell)

    pipe = p.communicate(input, timeout)

    pipe_out = b''
    if stdout == PIPE:
        pipe_out = pipe[0]

    pipe_err = b''
    if stderr == PIPE:
        pipe_err = pipe[1]

    str_out = pipe_out.decode(decode).replace('\r\n', '\n').strip()
    str_err = pipe_err.decode(decode).replace('\r\n', '\n').strip()

    out_msg = f"returned (out):\n{str_out}"
    if str_out:
        debug.message(out_msg, flag)

    if str_err:
        from sys import stderr
        err_msg = f"returned (err):\n{str_err}"
        # this message will also be send to syslog via airbag
        debug.message(err_msg, flag, destination=stderr)

        # should something go wrong, report this too via airbag
        airbag.noteworthy(cmd_msg)
        airbag.noteworthy(out_msg)
        airbag.noteworthy(err_msg)

    return str_out, p.returncode


def run(command, flag='', shell=None, input=None, timeout=None, env=None,
        stdout=DEVNULL, stderr=PIPE, decode='utf-8'):
    """
    A wrapper around popen, which discard the stdout and
    will return the error code of a command
    """
    _, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    return code


def cmd(command, flag='', shell=None, input=None, timeout=None, env=None,
        stdout=PIPE, stderr=PIPE, decode='utf-8', raising=None, message='',
        expect=[0]):
    """
    A wrapper around popen, which returns the stdout and
    will raise the error code of a command

    raising: specify which call should be used when raising
             the class should only require a string as parameter
             (default is OSError) with the error code
    expect:  a list of error codes to consider as normal
    """
    decoded, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    if code not in expect:
        feedback = message + '\n' if message else ''
        feedback += f'failed to run command: {command}\n'
        feedback += f'returned: {decoded}\n'
        feedback += f'exit code: {code}'
        if raising is None:
            # error code can be recovered with .errno
            raise OSError(code, feedback)
        else:
            raise raising(feedback)
    return decoded


def rc_cmd(command, flag='', shell=None, input=None, timeout=None, env=None,
           stdout=PIPE, stderr=STDOUT, decode='utf-8'):
    """
    A wrapper around popen, which returns the return code
    of a command and stdout

    % rc_cmd('uname')
    (0, 'Linux')
    % rc_cmd('ip link show dev eth99')
    (1, 'Device "eth99" does not exist.')
    """
    out, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    return code, out

def call(command, flag='', shell=None, input=None, timeout=None, env=None,
         stdout=None, stderr=None, decode='utf-8'):
    """
    A wrapper around popen, which print the stdout and
    will return the error code of a command
    """
    out, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    if out:
        print(out)
    return code

def process_running(pid_file):
    """ Checks if a process with PID in pid_file is running """
    from psutil import pid_exists
    if not os.path.isfile(pid_file):
        return False
    with open(pid_file, 'r') as f:
        pid = f.read().strip()
    return pid_exists(int(pid))

def process_named_running(name: str, cmdline: str=None, timeout: int=0):
    """ Checks if process with given name is running and returns its PID.
    If Process is not running, return None
    """
    from psutil import process_iter
    def check_process(name, cmdline):
        for p in process_iter(['name', 'pid', 'cmdline']):
            if cmdline:
                if name in p.info['name'] and cmdline in p.info['cmdline']:
                    return p.info['pid']
            elif name in p.info['name']:
                return p.info['pid']
        return None
    if timeout:
        import time
        time_expire = time.time() + timeout
        while True:
            tmp = check_process(name, cmdline)
            if not tmp:
                if time.time() > time_expire:
                    break
                time.sleep(0.100) # wait 100ms
                continue
            return tmp
    else:
        return check_process(name, cmdline)
    return None

def is_systemd_service_active(service):
    """ Test is a specified systemd service is activated.
    Returns True if service is active, false otherwise.
    Copied from: https://unix.stackexchange.com/a/435317 """
    tmp = cmd(f'systemctl show --value -p ActiveState {service}')
    return bool((tmp == 'active'))

def is_systemd_service_running(service):
    """ Test is a specified systemd service is actually running.
    Returns True if service is running, false otherwise.
    Copied from: https://unix.stackexchange.com/a/435317 """
    tmp = cmd(f'systemctl show --value -p SubState {service}')
    return bool((tmp == 'running'))

def ip_cmd(args, json=True):
    """ A helper for easily calling iproute2 commands """
    if json:
        from json import loads
        res = cmd(f"ip --json {args}").strip()
        if res:
            return loads(res)
        else:
            # Many mutation commands like "ip link set"
            # return an empty string
            return None
    else:
        res = cmd(f"ip {args}")
        return res
