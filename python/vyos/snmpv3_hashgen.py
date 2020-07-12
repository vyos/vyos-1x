# Copyright [2017] [Adam Bishop]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Imported from https://github.com/TheMysteriousX/SNMPv3-Hash-Generator

import hashlib
import string
import secrets

from itertools import repeat

P_LEN = 32
E_LEN = 16

class Hashgen(object):
    @staticmethod
    def md5(bytes):
        return hashlib.md5(bytes).digest().hex()

    @staticmethod
    def sha1(bytes):
        return hashlib.sha1(bytes).digest().hex()

    @staticmethod
    def expand(s, l):
        reps = l // len(s) + 1 # approximation; worst case: overrun = l + len(s)
        return ''.join(list(repeat(s, reps)))[:l]

    @classmethod
    def kdf(cls, password):
        data = cls.expand(password, 1048576).encode('utf-8')
        return hashlib.sha1(data).digest()

    @staticmethod
    def random_string(len=P_LEN, alphabet=(string.ascii_letters + string.digits)):
        return ''.join(secrets.choice(alphabet) for _ in range(len))

    @staticmethod
    def random_engine(len=E_LEN):
        return secrets.token_hex(len)

    @classmethod
    def derive_msg(cls, passphrase, engine):
        # Parameter derivation á la rfc3414
        Ku = cls.kdf(passphrase)
        E = bytearray.fromhex(engine)

        return b''.join([Ku, E, Ku])

    # Define available hash algorithms
    algs = {
        'sha1': sha1,
        'md5': md5,
    }
