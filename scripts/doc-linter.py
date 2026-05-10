import os
import re
import ipaddress
import sys
import ast

IPV4SEG  = r'(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])'
IPV4ADDR = r'\b(?:(?:' + IPV4SEG + r'\.){3,3}' + IPV4SEG + r')\b'
IPV6SEG  = r'(?:(?:[0-9a-fA-F]){1,4})'
IPV6GROUPS = (
    r'(?:' + IPV6SEG + r':){7,7}' + IPV6SEG,                  # 1:2:3:4:5:6:7:8
    r'(?:\s' + IPV6SEG + r':){1,7}:',                           # 1::                                 1:2:3:4:5:6:7::
    r'(?:' + IPV6SEG + r':){1,6}:' + IPV6SEG,                 # 1::8               1:2:3:4:5:6::8   1:2:3:4:5:6::8
    r'(?:' + IPV6SEG + r':){1,5}(?::' + IPV6SEG + r'){1,2}',  # 1::7:8             1:2:3:4:5::7:8   1:2:3:4:5::8
    r'(?:' + IPV6SEG + r':){1,4}(?::' + IPV6SEG + r'){1,3}',  # 1::6:7:8           1:2:3:4::6:7:8   1:2:3:4::8
    r'(?:' + IPV6SEG + r':){1,3}(?::' + IPV6SEG + r'){1,4}',  # 1::5:6:7:8         1:2:3::5:6:7:8   1:2:3::8
    r'(?:' + IPV6SEG + r':){1,2}(?::' + IPV6SEG + r'){1,5}',  # 1::4:5:6:7:8       1:2::4:5:6:7:8   1:2::8
    IPV6SEG + r':(?:(?::' + IPV6SEG + r'){1,6})',             # 1::3:4:5:6:7:8     1::3:4:5:6:7:8   1::8
    r':(?:(?::' + IPV6SEG + r'){1,7}|:)',                     # ::2:3:4:5:6:7:8    ::2:3:4:5:6:7:8  ::8       ::
    r'fe80:(?::' + IPV6SEG + r'){0,4}%[0-9a-zA-Z]{1,}',       # fe80::7:8%eth0     fe80::7:8%1  (link-local IPv6 addresses with zone index)
    r'::(?:ffff(?::0{1,4}){0,1}:){0,1}[^\s:]' + IPV4ADDR,     # ::255.255.255.255  ::ffff:255.255.255.255  ::ffff:0:255.255.255.255 (IPv4-mapped IPv6 addresses and IPv4-translated addresses)
    r'(?:' + IPV6SEG + r':){1,4}:[^\s:]' + IPV4ADDR,          # 2001:db8:3:4::192.0.2.33  64:ff9b::192.0.2.33 (IPv4-Embedded IPv6 Address)
)
IPV6ADDR = '|'.join(['(?:{})'.format(g) for g in IPV6GROUPS[::-1]])  # Reverse rows for greedy match

MAC = r'([0-9A-F]{2}[:-]){5}([0-9A-F]{2})'

NUMBER = r"([\s']\d+[\s'])"


def lint_mac(cnt, line):
    mac = re.search(MAC, line, re.I)
    if mac is not None:
        mac = mac.group()
        u_mac = re.search(r'((00)[:-](53)([:-][0-9A-F]{2}){4})', mac, re.I)
        m_mac = re.search(r'((90)[:-](10)([:-][0-9A-F]{2}){4})', mac, re.I)
        if u_mac is None and m_mac is None:
            return (f"Use MAC reserved for Documentation (RFC7042): {mac}", cnt, 'error')


def lint_ipv4(cnt, line):
    ip = re.search(IPV4ADDR, line, re.I)
    if ip is not None:
        ip = ipaddress.ip_address(ip.group().strip(' '))
        # https://docs.python.org/3/library/ipaddress.html#ipaddress.IPv4Address.is_private
        if ip.is_private:
            return None
        if ip.is_multicast:
            return None
        if ip.is_global is False:
            return None
        return (f"Use IPv4 reserved for Documentation (RFC 5737) or private Space: {ip}", cnt, 'error')


def lint_ipv6(cnt, line):
    ip = re.search(IPV6ADDR, line, re.I)
    if ip is not None:
        ip = ipaddress.ip_address(ip.group().strip(' '))
        if ip.is_private:
            return None
        if ip.is_multicast:
            return None
        if ip.is_global is False:
            return None
        return (f"Use IPv6 reserved for Documentation (RFC 3849) or private Space: {ip}", cnt, 'error')


def lint_AS(cnt, line):
    number = re.search(NUMBER, line, re.I)
    if number:
        pass
        # find a way to detect AS numbers


def lint_linelen(cnt, line):
    line = line.rstrip()
    if len(line) > 80:
        return (f"Line too long: len={len(line)}", cnt, 'warning')

def handle_file_action(filepath):
    errors = []
    try:
        with open(filepath) as fp:
            line = fp.readline()
            cnt = 1
            test_line_lenght = True
            start_vyoslinter = True
            indentation = 0
            while line:
                # search for ignore linter comments in lines
                if ".. stop_vyoslinter" in line:
                    start_vyoslinter = False
                if ".. start_vyoslinter" in line:
                    start_vyoslinter = True
                if start_vyoslinter:
                    # ignore every '.. code-block::' for line lenght
                    # rst code-block have its own style in html the format in rst
                    # and the build page must be the same
                    if test_line_lenght is False:
                        if len(line) > indentation:
                            #print(f"'{line}'")
                            #print(indentation)
                            if line[indentation].isspace() is False:
                                test_line_lenght = True

                    if ".. code-block::" in line:
                        test_line_lenght = False
                        indentation = 0
                        for i in line:
                            if i.isspace():
                                indentation = indentation + 1
                            else:
                                break
                    
                    err_mac = lint_mac(cnt, line.strip())
                    # disable mac detection for the moment, too many false positives
                    err_mac = None
                    err_ip4 = lint_ipv4(cnt, line.strip())
                    err_ip6 = lint_ipv6(cnt, line.strip())
                    if test_line_lenght:
                        err_len = lint_linelen(cnt, line)
                    else:
                        err_len = None
                    if err_mac:
                        errors.append(err_mac)
                    if err_ip4:
                        errors.append(err_ip4)
                    if err_ip6:
                        errors.append(err_ip6)
                    if err_len:
                        errors.append(err_len)
                
                line = fp.readline()
                cnt += 1
            
            # ensure linter was not stop on top and forgot to tun on again
            if start_vyoslinter == False:
                errors.append((f"Don't forgett to turn linter back on", cnt, 'error'))
    finally:
        fp.close()

    if len(errors) > 0:
        '''
        "::{$type} file={$filename},line={$line},col=$column::{$log}"
        '''
        print(f"File: {filepath}")
        for error in errors:
            print(f"::{error[2]} file={filepath},line={error[1]}::{error[0]}")
        print('')
        return False


def main():
    bool_error = True
    print('start')
    try:
        files = ast.literal_eval(sys.argv[1])
        for file in files:
                if file[-4:] in [".rst", ".txt"] and "_build" not in file:
                    if handle_file_action(file) is False:
                        bool_error = False
    except Exception as e:
        for root, dirs, files in os.walk("docs"):
            path = root.split(os.sep)
            for file in files:
                if file[-4:] in [".rst", ".txt"] and "_build" not in path:
                    fpath = '/'.join(path)
                    filepath = f"{fpath}/{file}"
                    if handle_file_action(filepath) is False:
                        bool_error = False

    return bool_error


if __name__ == "__main__":
    if main() == False:
        exit(1)
