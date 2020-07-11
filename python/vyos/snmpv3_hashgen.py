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
