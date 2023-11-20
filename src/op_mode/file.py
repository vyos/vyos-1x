#!/usr/bin/python3

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

import argparse
import contextlib
import datetime
import grp
import os
import pwd
import shutil
import sys
import tempfile

from vyos.remote import download
from vyos.remote import upload
from vyos.utils.io import ask_yes_no
from vyos.utils.io import print_error
from vyos.utils.process import cmd
from vyos.utils.process import run


parser = argparse.ArgumentParser(description='view, copy or remove files and directories',
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.epilog = """
TYPE is one of 'remote', 'image' and 'local'.
A local path is <path> or ~/<path>.
A remote path is <scheme>://<urn>.
An image path is <image>:<path>.

Clone operation is between images only.
Copy operation does not support directories from remote locations.
Delete operation does not support remote paths.
"""
operations = parser.add_mutually_exclusive_group(required=True)
operations.add_argument('--show', nargs=1, help='show the contents of file PATH of type TYPE',
                        metavar=('PATH'))
operations.add_argument('--copy', nargs=2, help='copy SRC to DEST',
                        metavar=('SRC', 'DEST'))
operations.add_argument('--delete', nargs=1, help='delete file PATH',
                        metavar=('PATH'))
operations.add_argument('--clone', help='clone config from running image to IMG',
                        metavar='IMG')
operations.add_argument('--clone-from', nargs=2, help='clone config from image SRC to image DEST',
                        metavar=('SRC', 'DEST'))

## Helper procedures
def fix_terminal() -> None:
    """
    Reset terminal after potential breakage caused by abrupt exits.
    """
    run('stty sane')

def get_types(arg: str) -> tuple[str, str]:
    """
    Determine whether the argument shows a local, image or remote path.
    """
    schemes = ['http', 'https', 'ftp', 'ftps', 'sftp', 'ssh', 'scp', 'tftp']
    s = arg.split("://", 1)
    if len(s) != 2:
        return 'local', arg
    elif s[0] in schemes:
        return 'remote', arg
    else:
        return 'image', arg

def zealous_copy(source: str, destination: str) -> None:
    # Even shutil.copy2() doesn't preserve ownership across copies.
    # So we need to resort to this.
    stats = os.stat(source)
    shutil.copy2(source, destination)
    os.chown(destination, stats.st_uid, stats.st_gid)

def get_file_type(path: str) -> str:
    return cmd(['file', '-sb', path])

def print_header(string: str) -> None:
    print('#' * 10, string, '#' * 10)

def octal_to_symbolic(octal: str) -> str:
    perms = ['---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx']
    result = ""
    # We discard all but the last three digits because we're only
    # interested in the permission bits.
    for i in octal[-3:]:
        result += perms[int(i)]
    return result

def get_user_and_group(stats: os.stat_result) -> tuple[str, str]:
    try:
        user = pwd.getpwuid(stats.st_uid).pw_name
    except (KeyError, PermissionError):
        user = str(stats.st_uid)
    try:
        group = grp.getgrgid(stats.st_gid).gr_name
    except (KeyError, PermissionError):
        group = str(stats.st_gid)
    return user, group

def print_file_info(path: str) -> None:
    stats = os.stat(path)
    username, groupname = get_user_and_group(stats)
    mtime = datetime.datetime.fromtimestamp(stats.st_mtime).strftime("%F %X")
    print_header('FILE INFO')
    print(f'Path:\t\t{path}')
    # File type is determined through `file(1)`.
    print(f'Type:\t\t{get_file_type(path)}')
    # Owner user and group
    print(f'Owner:\t\t{username}:{groupname}')
    # Permissions are converted from raw int to octal string to symbolic string.
    print(f'Permissions:\t{octal_to_symbolic(oct(stats.st_mode))}')
    # Last date of modification
    print(f'Modified:\t{mtime}')

def print_file_data(path: str) -> None:
    print_header('FILE DATA')
    file_type = get_file_type(path)
    # Human-readable files are streamed line-by-line.
    if 'text' in file_type:
        with open(path, 'r') as f:
            for line in f:
                print(line, end='')
    # tcpdump files go to TShark.
    elif 'pcap' in file_type or os.path.splitext(path)[1] == '.pcap':
        print(cmd(['sudo', 'tshark', '-r', path]))
    # All other binaries get hexdumped.
    else:
        print(cmd(['hexdump', '-C', path]))

def parse_image_path(image_path: str) -> str:
    """
    my-image:/foo/bar -> /lib/live/mount/persistence/boot/my-image/rw/foo/bar
    """
    image_name, path = image_path.split('://', 1)
    if image_name == 'running':
        image_root = '/'
    elif image_name == 'disk-install':
        image_root = '/lib/live/mount/persistence/'
    else:
        image_root = os.path.join('/lib/live/mount/persistence/boot', image_name, 'rw')
        if not os.path.isdir(image_root):
            print_error(f'Image {image_name} not found.')
            sys.exit(1)
    return os.path.join(image_root, path)


## Show procedures
def show_locally(path: str) -> None:
    """
    Display the contents of a local file or directory.
    """
    location = os.path.realpath(os.path.expanduser(path))
    # Temporarily redirect stdout to a throwaway file for `less(1)` to read.
    # The output could be potentially too hefty for an in-memory StringIO.
    temp = tempfile.NamedTemporaryFile('w', delete=False)
    try:
        with contextlib.redirect_stdout(temp):
            # Just a directory. Call `ls(1)` and bail.
            if os.path.isdir(location):
                print_header('DIRECTORY LISTING')
                print('Path:\t', location)
                print(cmd(['ls', '-hlFGL', '--group-directories-first', location]))
            elif os.path.isfile(location):
                print_file_info(location)
                print()
                print_file_data(location)
            else:
                print_error(f'File or directory {path} not found.')
                sys.exit(1)
            sys.stdout.flush()
        # Call `less(1)` and wait for it to terminate before going forward.
        cmd(['/usr/bin/less', '-X', temp.name], stdout=sys.stdout)
    # The stream to the temporary file could break for any reason.
    # It's much less fragile than if we streamed directly to the process stdin.
    # But anything could still happen and we don't want to scare the user.
    except (BrokenPipeError, EOFError, KeyboardInterrupt, OSError):
        fix_terminal()
        sys.exit(1)
    finally:
        os.remove(temp.name)

def show(type: str, path: str) -> None:
    if type == 'remote':
        temp = tempfile.NamedTemporaryFile(delete=False)
        download(temp.name, path)
        show_locally(temp.name)
        os.remove(temp.name)
    elif type == 'image':
        show_locally(parse_image_path(path))
    elif type == 'local':
        show_locally(path)
    else:
        print_error(f'Unknown target for showing: {type}')
        print_error('Valid types are "remote", "image" and "local".')
        sys.exit(1)


## Copying procedures
def copy(source_type: str, source_path: str,
         destination_type: str, destination_path: str) -> None:
    """
    Copy a file or directory locally, remotely or to and from an image.
    Directory uploads and downloads not supported.
    """
    source = ''
    try:
        # Download to a temporary file and use that as the source.
        if source_type == 'remote':
            source = tempfile.NamedTemporaryFile(delete=False).name
            download(source, source_path)
        # Prepend the image root to the path.
        elif source_type == 'image':
            source = parse_image_path(source_path)
        elif source_type == 'local':
            source = source_path
        else:
            print_error(f'Unknown source type: {source_type}')
            print_error(f'Valid source types are "remote", "image" and "local".')
            sys.exit(1)

        # Directly upload the file.
        if destination_type == 'remote':
            if os.path.isdir(source):
                print_error(f'Cannot upload {source}. Directory uploads not supported.')
                sys.exit(1)
            upload(source, destination_path)
        # No need to duplicate local copy operations for image copying.
        elif destination_type == 'image':
            copy('local', source, 'local', parse_image_path(destination_path))
        # Try to preserve metadata when copying.
        elif destination_type == 'local':
            if os.path.isdir(destination_path):
                destination_path = os.path.join(destination_path, os.path.basename(source))
            if os.path.isdir(source):
                shutil.copytree(source, destination_path, copy_function=zealous_copy)
            else:
                zealous_copy(source, destination_path)
        else:
            print_error(f'Unknown destination type: {source_type}')
            print_error(f'Valid destination types are "remote", "image" and "local".')
            sys.exit(1)
    except OSError:
        import traceback
        # We can't check for every single user error (eg copying a directory to a file)
        #  so we just let a curtailed stack trace provide a descriptive error.
        print_error(f'Failed to copy {source_path} to {destination_path}.')
        traceback.print_exception(*sys.exc_info()[:2], None)
        sys.exit(1)
    else:
        # To prevent a duplicate message.
        if destination_type != 'image':
            print('Copy successful.')
    finally:
        # Clean up temporary file.
        if source_type == 'remote':
            os.remove(source)


## Deletion procedures
def delete_locally(path: str) -> None:
    """
    Remove a local file or directory.
    """
    try:
        if os.path.isdir(path):
            if (ask_yes_no(f'Do you want to remove {path} with all its contents?')):
                shutil.rmtree(path)
                print(f'Directory {path} removed.')
            else:
                print('Operation aborted.')
        elif os.path.isfile(path):
            if (ask_yes_no(f'Do you want to remove {path}?')):
                os.remove(path)
                print(f'File {path} removed.')
            else:
                print('Operation aborted.')
        else:
            raise OSError(f'File or directory {path} not found.')
    except OSError:
        import traceback
        print_error(f'Failed to delete {path}.')
        traceback.print_exception(*sys.exc_info()[:2], None)
        sys.exit(1)

def delete(type: str, path: str) -> None:
    if type == 'local':
        delete_locally(path)
    elif type == 'image':
        delete_locally(parse_image_path(path))
    else:
        print_error(f'Unknown target for deletion: {type}')
        print_error('Valid types are "image" and "local".')
        sys.exit(1)


## Cloning procedures
def clone(source: str, destination: str) -> None:
    if os.geteuid():
        print_error('Only the superuser can run this command.')
        sys.exit(1)
    if destination == 'running' or destination == 'disk-install':
        print_error(f'Cannot clone config to {destination}.')
        sys.exit(1)
    # If `source` is None, then we're going to copy from the running image.
    if source is None or source == 'running':
        source_path = '/config'
        # For the warning message only.
        source = 'the current'
    else:
        source_path = parse_image_path(source + ':/config')
    destination_path = parse_image_path(destination + ':/config')
    backup_path = destination_path + '.preclone'

    if not os.path.isdir(source_path):
        print_error(f'Source image {source} does not exist.')
        sys.exit(1)
    if not os.path.isdir(destination_path):
        print_error(f'Destination image {destination} does not exist.')
        sys.exit(1)
    print(f'WARNING: This operation will erase /config data in image {destination}.')
    print(f'/config data in {source} image will be copied over in its place.')
    print(f'The existing /config data in {destination} image will be backed up to /config.preclone.')

    if ask_yes_no('Are you sure you want to continue?'):
        try:
            if os.path.isdir(backup_path):
                print('Removing previous backup...')
                shutil.rmtree(backup_path)
            print('Making new backup...')
            shutil.move(destination_path, backup_path)
        except:
            print('Something went wrong during the backup process!')
            print('Cowardly refusing to proceed with cloning.')
            raise
        # Copy new config from image.
        try:
            shutil.copytree(source_path, destination_path, copy_function=zealous_copy)
        except:
            print('Cloning failed! Reverting to backup!')
            # Delete leftover files from the botched cloning.
            shutil.rmtree(destination_path, ignore_errors=True)
            # Restore backup before bailing out.
            shutil.copytree(backup_path, destination_path, copy_function=zealous_copy)
            raise
        else:
            print(f'Successfully cloned config from {source} to {destination}.')
        finally:
            shutil.rmtree(backup_path)
    else:
        print('Operation aborted.')

if __name__ == '__main__':
    args = parser.parse_args()
    try:
        if args.show:
            show(*get_types(args.show[0]))
        elif args.copy:
            copy(*get_types(args.copy[0]),
                 *get_types(args.copy[1]))
        elif args.delete:
            delete(*get_types(args.delete[0]))
        elif args.clone_from:
            clone(*args.clone_from)
        elif args.clone:
            # Pass None as source image to copy from local image.
            clone(None, args.clone)
    except KeyboardInterrupt:
        print_error('Operation cancelled by user.')
        sys.exit(1)
    sys.exit(0)
