# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import datetime
import ipaddress

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import NameOID
from cryptography.x509.oid import ExtendedKeyUsageOID
from cryptography.x509.oid import ExtensionOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa

CERT_BEGIN='-----BEGIN CERTIFICATE-----\n'
CERT_END='\n-----END CERTIFICATE-----'
KEY_BEGIN='-----BEGIN PRIVATE KEY-----\n'
KEY_END='\n-----END PRIVATE KEY-----'
KEY_EC_BEGIN='-----BEGIN EC PRIVATE KEY-----\n'
KEY_EC_END='\n-----END EC PRIVATE KEY-----'
KEY_ENC_BEGIN='-----BEGIN ENCRYPTED PRIVATE KEY-----\n'
KEY_ENC_END='\n-----END ENCRYPTED PRIVATE KEY-----'
KEY_PUB_BEGIN='-----BEGIN PUBLIC KEY-----\n'
KEY_PUB_END='\n-----END PUBLIC KEY-----'
CRL_BEGIN='-----BEGIN X509 CRL-----\n'
CRL_END='\n-----END X509 CRL-----'
CSR_BEGIN='-----BEGIN CERTIFICATE REQUEST-----\n'
CSR_END='\n-----END CERTIFICATE REQUEST-----'
DH_BEGIN='-----BEGIN DH PARAMETERS-----\n'
DH_END='\n-----END DH PARAMETERS-----'
OVPN_BEGIN = '-----BEGIN OpenVPN Static key V{0}-----\n'
OVPN_END = '\n-----END OpenVPN Static key V{0}-----'
OPENSSH_KEY_BEGIN='-----BEGIN OPENSSH PRIVATE KEY-----\n'
OPENSSH_KEY_END='\n-----END OPENSSH PRIVATE KEY-----'

# Print functions

encoding_map = {
    'PEM': serialization.Encoding.PEM,
    'OpenSSH': serialization.Encoding.OpenSSH
}

public_format_map = {
    'SubjectPublicKeyInfo': serialization.PublicFormat.SubjectPublicKeyInfo,
    'OpenSSH': serialization.PublicFormat.OpenSSH
}

private_format_map = {
    'PKCS8': serialization.PrivateFormat.PKCS8,
    'OpenSSH': serialization.PrivateFormat.OpenSSH
}

hash_map = {
    'sha256': hashes.SHA256,
    'sha384': hashes.SHA384,
    'sha512': hashes.SHA512,
}

def get_certificate_fingerprint(cert, hash):
    hash_algorithm = hash_map[hash]()
    fp = cert.fingerprint(hash_algorithm)

    return fp.hex(':').upper()

def encode_certificate(cert):
    return cert.public_bytes(encoding=serialization.Encoding.PEM).decode('utf-8')

def encode_public_key(cert, encoding='PEM', key_format='SubjectPublicKeyInfo'):
    if encoding not in encoding_map:
        encoding = 'PEM'
    if key_format not in public_format_map:
        key_format = 'SubjectPublicKeyInfo'
    return cert.public_bytes(
        encoding=encoding_map[encoding],
        format=public_format_map[key_format]).decode('utf-8')

def encode_private_key(private_key, encoding='PEM', key_format='PKCS8', passphrase=None):
    if encoding not in encoding_map:
        encoding = 'PEM'
    if key_format not in private_format_map:
        key_format = 'PKCS8'
    encryption = serialization.NoEncryption() if not passphrase else serialization.BestAvailableEncryption(bytes(passphrase, 'utf-8'))
    return private_key.private_bytes(
        encoding=encoding_map[encoding],
        format=private_format_map[key_format],
        encryption_algorithm=encryption).decode('utf-8')

def encode_dh_parameters(dh_parameters):
    return dh_parameters.parameter_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.ParameterFormat.PKCS3).decode('utf-8')

# EC Helper

def get_elliptic_curve(size):
    curve_func = None
    name = f'SECP{size}R1'
    if hasattr(ec, name):
        curve_func = getattr(ec, name)
    else:
        curve_func = ec.SECP256R1() # Default to SECP256R1
    return curve_func()

# Creation functions

def create_private_key(key_type, key_size=None):
    private_key = None
    if key_type == 'rsa':
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    elif key_type == 'dsa':
        private_key = dsa.generate_private_key(key_size=key_size)
    elif key_type == 'ec':
        curve = get_elliptic_curve(key_size)
        private_key = ec.generate_private_key(curve)
    return private_key

def create_certificate_request(subject, private_key, subject_alt_names=[]):
    subject_obj = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, subject['country']),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, subject['state']),
        x509.NameAttribute(NameOID.LOCALITY_NAME, subject['locality']),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, subject['organization']),
        x509.NameAttribute(NameOID.COMMON_NAME, subject['common_name'])])

    builder = x509.CertificateSigningRequestBuilder() \
        .subject_name(subject_obj)

    if subject_alt_names:
        alt_names = []
        for obj in subject_alt_names:
            if isinstance(obj, ipaddress.IPv4Address) or isinstance(obj, ipaddress.IPv6Address):
                alt_names.append(x509.IPAddress(obj))
            elif isinstance(obj, str):
                alt_names.append(x509.RFC822Name(obj) if '@' in obj else x509.DNSName(obj))
        if alt_names:
            builder = builder.add_extension(x509.SubjectAlternativeName(alt_names), critical=False)

    return builder.sign(private_key, hashes.SHA256())

def add_key_identifier(ca_cert):
    try:
        ski_ext = ca_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        return x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski_ext.value)
    except:
        return x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key())

def create_certificate(cert_req, ca_cert, ca_private_key, valid_days=365, cert_type='server', is_ca=False, is_sub_ca=False):
    ext_key_usage = []
    if is_ca:
        ext_key_usage = [ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]
    elif cert_type == 'client':
        ext_key_usage = [ExtendedKeyUsageOID.CLIENT_AUTH]
    elif cert_type == 'server':
        ext_key_usage = [ExtendedKeyUsageOID.SERVER_AUTH]

    builder = x509.CertificateBuilder() \
        .subject_name(cert_req.subject) \
        .issuer_name(ca_cert.subject) \
        .public_key(cert_req.public_key()) \
        .serial_number(x509.random_serial_number()) \
        .not_valid_before(datetime.datetime.utcnow()) \
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=int(valid_days)))

    builder = builder.add_extension(x509.BasicConstraints(ca=is_ca, path_length=0 if is_sub_ca else None), critical=True)
    builder = builder.add_extension(x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=is_ca,
        crl_sign=is_ca,
        encipher_only=False,
        decipher_only=False), critical=True)
    builder = builder.add_extension(x509.ExtendedKeyUsage(ext_key_usage), critical=False)
    builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(cert_req.public_key()), critical=False)

    if not is_ca or is_sub_ca:
        builder = builder.add_extension(add_key_identifier(ca_cert), critical=False)

    for ext in cert_req.extensions:
        builder = builder.add_extension(ext.value, critical=False)

    return builder.sign(ca_private_key, hashes.SHA256())

def create_certificate_revocation_list(ca_cert, ca_private_key, serial_numbers=[]):
    if not serial_numbers:
        return False

    builder = x509.CertificateRevocationListBuilder() \
        .issuer_name(ca_cert.subject) \
        .last_update(datetime.datetime.today()) \
        .next_update(datetime.datetime.today() + datetime.timedelta(1, 0, 0))

    for serial_number in serial_numbers:
        revoked_cert = x509.RevokedCertificateBuilder() \
            .serial_number(serial_number) \
            .revocation_date(datetime.datetime.today()) \
            .build()
        builder = builder.add_revoked_certificate(revoked_cert)

    return builder.sign(private_key=ca_private_key, algorithm=hashes.SHA256())

def create_dh_parameters(bits=2048):
    if not bits or bits < 512:
        print("Invalid DH parameter key size")
        return False

    return dh.generate_parameters(generator=2, key_size=int(bits))

# Wrap functions

def wrap_public_key(raw_data):
    return KEY_PUB_BEGIN + raw_data + KEY_PUB_END

def wrap_private_key(raw_data, passphrase=None, ec=False):
    begin = KEY_BEGIN
    end = KEY_END

    if passphrase:
        begin = KEY_ENC_BEGIN
        end = KEY_ENC_END
    elif ec:
        begin = KEY_EC_BEGIN
        end = KEY_EC_END

    return begin + raw_data + end

def wrap_openssh_public_key(raw_data, type):
    return f'{type} {raw_data}'

def wrap_openssh_private_key(raw_data):
    return OPENSSH_KEY_BEGIN + raw_data +  OPENSSH_KEY_END

def wrap_certificate_request(raw_data):
    return CSR_BEGIN + raw_data + CSR_END

def wrap_certificate(raw_data):
    return CERT_BEGIN + raw_data + CERT_END

def wrap_crl(raw_data):
    return CRL_BEGIN + raw_data + CRL_END

def wrap_dh_parameters(raw_data):
    return DH_BEGIN + raw_data + DH_END

def wrap_openvpn_key(raw_data, version='1'):
    return OVPN_BEGIN.format(version) + raw_data + OVPN_END.format(version)

# Load functions
def load_public_key(raw_data, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_public_key(raw_data)

    try:
        return serialization.load_pem_public_key(bytes(raw_data, 'utf-8'))
    except ValueError:
        return False

def _load_private_key(raw_data, passphrase):
    try:
        return serialization.load_pem_private_key(bytes(raw_data, 'utf-8'), password=passphrase)
    except (ValueError, TypeError):
        return False

def load_private_key(raw_data, passphrase=None, wrap_tags=True):
    if passphrase is not None:
        passphrase = bytes(passphrase, 'utf-8')

    result = False

    if wrap_tags:
        for ec_test in [False, True]:
            wrapped_data = wrap_private_key(raw_data, passphrase, ec_test)
            if result := _load_private_key(wrapped_data, passphrase):
                return result
        return False
    else:
        return _load_private_key(raw_data, passphrase)

def load_openssh_public_key(raw_data, type):
    try:
        return serialization.load_ssh_public_key(bytes(f'{type} {raw_data}', 'utf-8'))
    except ValueError:
        return False

def load_openssh_private_key(raw_data, passphrase=None, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_openssh_private_key(raw_data)

    try:
        return serialization.load_ssh_private_key(bytes(raw_data, 'utf-8'), password=passphrase)
    except ValueError:
        return False

def load_certificate_request(raw_data, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_certificate_request(raw_data)

    try:
        return x509.load_pem_x509_csr(bytes(raw_data, 'utf-8'))
    except ValueError:
        return False

def load_certificate(raw_data, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_certificate(raw_data)

    try:
        return x509.load_pem_x509_certificate(bytes(raw_data, 'utf-8'))
    except ValueError:
        return False

def load_crl(raw_data, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_crl(raw_data)

    try:
        return x509.load_pem_x509_crl(bytes(raw_data, 'utf-8'))
    except ValueError:
        return False

def load_dh_parameters(raw_data, wrap_tags=True):
    if wrap_tags:
        raw_data = wrap_dh_parameters(raw_data)

    try:
        return serialization.load_pem_parameters(bytes(raw_data, 'utf-8'))
    except ValueError:
        return False

# Verify

def is_ca_certificate(cert):
    if not cert:
        return False

    try:
        ext = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
        return ext.value.ca
    except ExtensionNotFound:
        return False

def verify_certificate(cert, ca_cert):
    # Verify certificate was signed by specified CA
    if ca_cert.subject != cert.issuer:
        return False

    ca_public_key = ca_cert.public_key()
    try:
        if isinstance(ca_public_key, rsa.RSAPublicKeyWithSerialization):
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding=padding.PKCS1v15(),
                algorithm=cert.signature_hash_algorithm)
        elif isinstance(ca_public_key, dsa.DSAPublicKeyWithSerialization):
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                algorithm=cert.signature_hash_algorithm)
        elif isinstance(ca_public_key, ec.EllipticCurvePublicKeyWithSerialization):
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                signature_algorithm=ec.ECDSA(cert.signature_hash_algorithm))
        else:
            return False # We cannot verify it
        return True
    except InvalidSignature:
        return False

def verify_crl(crl, ca_cert):
    # Verify CRL was signed by specified CA
    if ca_cert.subject != crl.issuer:
        return False

    ca_public_key = ca_cert.public_key()
    try:
        if isinstance(ca_public_key, rsa.RSAPublicKeyWithSerialization):
            ca_public_key.verify(
                crl.signature,
                crl.tbs_certlist_bytes,
                padding=padding.PKCS1v15(),
                algorithm=crl.signature_hash_algorithm)
        elif isinstance(ca_public_key, dsa.DSAPublicKeyWithSerialization):
            ca_public_key.verify(
                crl.signature,
                crl.tbs_certlist_bytes,
                algorithm=crl.signature_hash_algorithm)
        elif isinstance(ca_public_key, ec.EllipticCurvePublicKeyWithSerialization):
            ca_public_key.verify(
                crl.signature,
                crl.tbs_certlist_bytes,
                signature_algorithm=ec.ECDSA(crl.signature_hash_algorithm))
        else:
            return False # We cannot verify it
        return True
    except InvalidSignature:
        return False

def verify_ca_chain(sorted_names, pki_node):
    if len(sorted_names) == 1: # Single cert, no chain
        return True

    for name in sorted_names:
        cert = load_certificate(pki_node[name]['certificate'])
        verified = False
        for ca_name in sorted_names:
            if name == ca_name:
                continue
            ca_cert = load_certificate(pki_node[ca_name]['certificate'])
            if verify_certificate(cert, ca_cert):
                verified = True
                break
        if not verified and name != sorted_names[-1]:
            # Only permit top-most certificate to fail verify (e.g. signed by public CA not explicitly in chain)
            return False
    return True

# Certificate chain

def find_parent(cert, ca_certs):
    for ca_cert in ca_certs:
        if verify_certificate(cert, ca_cert):
            return ca_cert
    return None

def find_chain(cert, ca_certs):
    remaining = ca_certs.copy()
    chain = [cert]

    while remaining:
        parent = find_parent(chain[-1], remaining)
        if parent is None:
            # No parent in the list of remaining certificates or there's a circular dependency
            break
        elif parent == chain[-1]:
            # Self-signed: must be root CA (end of chain)
            break
        else:
            remaining.remove(parent)
            chain.append(parent)

    return chain

def sort_ca_chain(ca_names, pki_node):
    def ca_cmp(ca_name1, ca_name2, pki_node):
        cert1 = load_certificate(pki_node[ca_name1]['certificate'])
        cert2 = load_certificate(pki_node[ca_name2]['certificate'])

        if verify_certificate(cert1, cert2): # cert1 is child of cert2
            return -1
        return 1

    from functools import cmp_to_key
    return sorted(ca_names, key=cmp_to_key(lambda cert1, cert2: ca_cmp(cert1, cert2, pki_node)))
