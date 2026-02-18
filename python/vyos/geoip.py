
import csv
import gzip
import os
import sqlite3
import zipfile

from io import TextIOWrapper
from pathlib import Path
from time import strftime

from vyos.remote import download
from vyos.template import is_ipv4, render
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import run

nftables_geoip_conf = '/run/nftables-geoip.conf'
dbip_database_raw = '/usr/share/vyos-geoip/dbip-country-lite.csv.gz'
mm_database_raw = '/usr/share/vyos-geoip/maxmind-country.zip'
geoip_database_path = '/var/cache/vyos/geoip-lookup.db'
geoip_lock_file = '/var/lock/vyos-geoip.lock'

# Raw data

def geoip_download_dbip():
    url = 'https://download.db-ip.com/free/dbip-country-lite-{}.csv.gz'.format(strftime("%Y-%m"))
    try:
        dirname = os.path.dirname(dbip_database_raw)
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        download(dbip_database_raw, url)
        return True
    except:
        return False

def geoip_download_maxmind(account_id : str, license_key: str, lite : bool) -> bool:
    db_str = 'GeoLite2' if lite else 'GeoIP2'
    url = f'https://{account_id}:{license_key}@download.maxmind.com/geoip/databases/{db_str}-Country-CSV/download?suffix=zip'
    try:
        dirname = os.path.dirname(mm_database_raw)
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        download(mm_database_raw, url)
        return True
    except:
        return False

# VyOS database

def db_is_initialised():
    if not os.path.exists(geoip_database_path):
        return False

    with sqlite3.connect(geoip_database_path) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(geoip_ranges);")
        rows = cur.fetchall()
        return len(rows) > 0

def db_initialise():
    dirname = os.path.dirname(geoip_database_path)
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    with sqlite3.connect(geoip_database_path) as conn:
        cur = conn.cursor()
        cur.execute("""
                    CREATE TABLE IF NOT EXISTS geoip_ranges (
                        country_code TEXT NOT NULL,
                        range TEXT NOT NULL,
                        version INT NOT NULL
                    )
                    """)
        cur.execute('CREATE INDEX IF NOT EXISTS idx_cc_version ON geoip_ranges(country_code, version)')
        conn.commit()

def db_import_dbip_ranges(replace=True, delete_file=False):
    if not os.path.exists(dbip_database_raw):
        return False

    if not os.path.exists(geoip_database_path):
        return False

    try:
        with gzip.open(dbip_database_raw, mode='rt') as csv_fh:
            reader = csv.reader(csv_fh)

            with sqlite3.connect(geoip_database_path) as conn:
                cur = conn.cursor()

                if replace:
                    cur.execute('DELETE FROM geoip_ranges')

                for start, end, code in reader:
                    version = 4 if is_ipv4(start) else 6
                    cur.execute('INSERT INTO geoip_ranges (country_code, range, version) VALUES (?, ?, ?)', (code.lower(), f'{start}-{end}', version))
                conn.commit()

        if delete_file:
            os.unlink(dbip_database_raw)

        return True
    except:
        return False

def db_import_maxmind_ranges(replace=True, delete_file=False):
    if not os.path.exists(mm_database_raw):
        return False

    if not zipfile.is_zipfile(mm_database_raw):
        return False

    if not os.path.exists(geoip_database_path):
        return False

    try:
        with zipfile.ZipFile(mm_database_raw, mode='r') as zip_fh:
            directory = os.path.dirname(zip_fh.namelist()[0])
            prefix = 'GeoLite2' if any(f.startswith('GeoLite2') for f in zip_fh.namelist()) else 'GeoIP2'

            ipv4_file = f'{directory}/{prefix}-Country-Blocks-IPv4.csv'
            ipv6_file = f'{directory}/{prefix}-Country-Blocks-IPv6.csv'
            locations_file = f'{directory}/{prefix}-Country-Locations-en.csv'
            locations_map = {}

            with zip_fh.open(locations_file) as raw_csv_fh:
                with TextIOWrapper(raw_csv_fh, encoding='utf-8') as csv_fh:
                    reader = csv.DictReader(csv_fh)

                    for row in reader:
                        id = row['geoname_id']
                        locations_map[id] = row['country_iso_code']

            with sqlite3.connect(geoip_database_path) as conn:
                cur = conn.cursor()

                if replace:
                    cur.execute('DELETE FROM geoip_ranges')

                with zip_fh.open(ipv4_file) as raw_csv_fh:
                    with TextIOWrapper(raw_csv_fh, encoding='utf-8') as csv_fh:
                        reader = csv.DictReader(csv_fh)
                        for row in reader:
                            id = row['geoname_id']

                            if not id or id not in locations_map:
                                continue

                            code = locations_map[id]
                            cur.execute('INSERT INTO geoip_ranges (country_code, range, version) VALUES (?, ?, 4)', (code.lower(), row['network']))

                with zip_fh.open(ipv6_file) as raw_csv_fh:
                    with TextIOWrapper(raw_csv_fh, encoding='utf-8') as csv_fh:
                        reader = csv.DictReader(csv_fh)
                        for row in reader:
                            id = row['geoname_id']

                            if not id or id not in locations_map:
                                continue

                            code = locations_map[id]
                            cur.execute('INSERT INTO geoip_ranges (country_code, range, version) VALUES (?, ?, 6)', (code.lower(), row['network']))

                conn.commit()

        if delete_file:
            os.unlink(mm_database_raw)

        return True
    except:
        return False

def db_return_ranges(codes, version):
    out = []
    with sqlite3.connect(geoip_database_path) as conn:
        cur = conn.cursor()
        ph = ','.join(['?'] * len(codes))
        for row in cur.execute(f'SELECT range FROM geoip_ranges WHERE version = ? AND country_code IN ({ph})', [version, *codes]):
            out.append(row[0])
    return out

# Update

def geoip_refresh():
    with GeoIPLock(geoip_lock_file) as lock:
        if not lock:
            return True

        if not os.path.exists(nftables_geoip_conf):
            return False

        result = run(f'nft --file {nftables_geoip_conf}')
        if result != 0:
            return False

        return True

def geoip_update(firewall=None, policy=None):
    with GeoIPLock(geoip_lock_file) as lock:
        if not lock:
            print("Script is already running")
            return False

        if not firewall and not policy:
            print("Firewall and policy are not configured")
            return True

        if not os.path.exists(geoip_database_path):
            print("Running one-time database initialisation")
            db_initialise()
            db_import_dbip_ranges()

        firewall_sets = {'v4': {}, 'v6': {}}
        policy_sets = {'v4': {}, 'v6': {}}

        if firewall:
            for codes, path in dict_search_recursive(firewall, 'country_code'):
                version = 6 if path[0] == 'ipv6' else 4
                vprefix = '6' if version == 6 else ''
                set_name = f'GEOIP_CC{vprefix}_{path[1]}_{path[2]}_{path[4]}'
                firewall_sets[f'v{version}'][set_name] = db_return_ranges(codes, version)

        if policy:
            for codes, path in dict_search_recursive(policy, 'country_code'):
                version = 6 if path[0] == 'route6' else 4
                vprefix = '6' if version == 6 else ''
                set_name = f'GEOIP_CC{vprefix}_{path[0]}_{path[1]}_{path[3]}'
                policy_sets[f'v{version}'][set_name] = db_return_ranges(codes, version)

        render(nftables_geoip_conf, 'firewall/nftables-geoip-update.j2', {
            'firewall_sets': firewall_sets,
            'policy_sets': policy_sets
        })

        result = run(f'nft --file {nftables_geoip_conf}')
        if result != 0:
            print('Error: GeoIP failed to update firewall and/or policy')
            return False

        return True

# Utility

class GeoIPLock(object):
    def __init__(self, file):
        self.file = file

    def __enter__(self):
        if os.path.exists(self.file):
            return False

        Path(self.file).touch()
        return True

    def __exit__(self, exc_type, exc_value, tb):
        os.unlink(self.file)
