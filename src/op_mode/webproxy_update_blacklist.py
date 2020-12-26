#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

#blacklist_url = 'ftp://ftp.univ-tlse1.fr/pub/reseau/cache/squidguard_contrib/blacklists.tar.gz'
blacklist_url = 'http://lnx01.mybll.net/~cpo/blacklists.tar.gz'
global_data_dir = '/config/url-filtering'
sg_dir = f'{global_data_dir}/squidguard'
blacklist_dir = f'{sg_dir}/db'
archive_dir = f'{sg_dir}/archive'
target_file = '/tmp/blacklists.tar.gz'

#
# XXX: this is a proof of concept for downloading a file via Python
#


import os
import shutil
import argparse
import urllib.request
import tarfile

from tqdm import tqdm
from vyos.util import chown
from vyos.util import chmod

parser = argparse.ArgumentParser()
parser.add_argument("--update", help="Update SquidGuard blacklist",
        action="store_true")
args = parser.parse_args()

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def download_url(url, output_path):
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

def squidguard_is_blacklist_installed():
    return os.path.exists(blacklist_dir)


def install_blacklist():
    download_url(blacklist_url, target_file)

    print('Uncompressing blacklist...')
    tar = tarfile.open(target_file, "r:gz")
    tar.extractall(path='/tmp')
    tar.close()

    if not os.path.exists(sg_dir):
        os.makedirs(sg_dir, exist_ok=True)

    if os.path.exists(archive_dir):
        print('Removing old archive...')
        shutil.rmtree(archive_dir)

    if os.path.exists(blacklist_dir):
        print('Archiving old blacklist...')
        shutil.move(blacklist_dir, archive_dir)

    shutil.move('/tmp/blacklists', blacklist_dir)

    chown(blacklist_dir, 'proxy', 'proxy')
    chmod(blacklist_dir, 0o755)


if args.update:
    if not squidguard_is_blacklist_installed():
        print('Warning: No url-filtering blacklist installed')
        input('Would you like to download a default blacklist? [confirm]')

    else:
        input('Would you like to re-download the blacklist? [confirm]')

    install_blacklist()
