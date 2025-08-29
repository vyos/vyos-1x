'''
NXP Wifi related utilities.
'''

import os
import subprocess
import re


def pcie_wifi_nxp_model() -> str:
    '''
    Returns NXP wifi PCIE model if one is installed, else ""

    This corresponds to the base section value in the config file
    /lib/firmware/nxp/wifi_mod_para.conf
    '''
    nxpmodel = ''
    if not os.path.exists('/sys/module/moal'):
        return nxpmodel  # Not using NXP at all

    # Get NXP wifi devices on PCI
    ret = subprocess.run(['lspci', '-vmm'], stdout=subprocess.PIPE)
    for i in ret.stdout.decode().split('\n'):
        if not i:
            continue
        tag, val = i.split(sep='\t', maxsplit=1)
        if tag != 'Device:':
            continue
        if 'NXP' not in val or 'Wi-Fi' not in val:
            continue

        # NXP wifi device.  Get the 4-digit model.
        m = re.match(r'.* [0-9][0-9][A-Z]([0-9]{4}).*', val)
        if m:
            try:
                nxpmodel = 'PCIE' + m.groups()[0]
                break
            except Exception:
                pass

    return nxpmodel


class NxpConf:
    '''
    NXP /lib/firmware/nxp/*.conf parser.

    The format is just:

    section = {
        foo = 42
        bar = baz
    }
    '''
    def __init__(self, path: str):
        self.path = path

    def parse(self) -> dict[str, dict]:
        '''Do the parse'''
        sectdict: dict[str, dict] = {}
        lineno = 0
        cursect: dict[str, str] = {}
        sectname = ''
        with open(self.path) as fp:
            for i in fp.readlines():
                lineno += 1
                i = i.strip()
                if not i or i.startswith('#'):
                    continue

                if not sectname:
                    # Section start "foo = {" expected
                    try:
                        sectname, _, brace = i.split(maxsplit=2)
                        if not brace.startswith('{'):
                            raise ValueError('Opening brace expected')
                    except ValueError:
                        raise ValueError('Expected "name = {" at line '
                                         f'{lineno}: {i}') from None
                    cursect = {}
                elif i == '}':
                    # End section
                    sectdict[sectname] = cursect
                    sectname, cursect = '', {}
                else:
                    # Inside a section
                    try:
                        name, val = i.split('=', 1)
                    except ValueError:
                        raise ValueError(f'Expected "name = val" at line '
                                         f'{lineno} in section {sectname}: '
                                         f'{i}') from None
                    cursect[name] = val

        return sectdict


def getphymac(wifi: dict) -> str:
    '''
    PSL: Get preferred MAC for phy if none provided by VyOS config.

    MACs cannot be programmed into some NXP devices.
    Rather than falling back to the default hardware
    /sys/class/ieee80211/*/addresses as VyOS normally does,
    use either any supplied module configuration value from
    /lib/firmware/nxp/wifi_mod_para.conf or else fall back to
    the existing interface address.

    For module configuration we are looking for config lines of the form:

    PCIE9098_0 = {
        ...
        mac_addr=00:40:02:01:02:03
        ...
    }

    ...for both PCIE9098_0 and PCIE9098_1 sections or however many phys
    the device has, in this case for a PCIE9098 card, but it can be
    any NXP model.

    NOTE: This function returns '' if we are not equipped with an
    NXP like device. VyOS will use the hardware address as usual.

    NOTE: generate() below masks off the lower 4 bits and rebuilds them,
    so the results will look a bit different than you might expect.
    '''

    hwmac = ''
    if 'mac' in wifi:
        # VyOS defined MAC already supplied
        return hwmac

    nxp_model = pcie_wifi_nxp_model()
    if not nxp_model:
        # Not NXP hardware so nothing to do
        return hwmac

    # Try NXP config file mac_addr
    try:
        nxpconf = NxpConf('/lib/firmware/nxp/wifi_mod_para.conf')
        nxpconfd = nxpconf.parse()
        phynum = wifi.get('physical_device', '0')[-1]
        ifc = f'{nxp_model}_{phynum}'
        hwmac = nxpconfd[ifc]['mac_addr']
    except Exception:
        pass

    if not hwmac:
        # Get mac from existing iface value instead
        import subprocess
        try:
            ret = subprocess.run(['ip', '-json', '-detail', 'link',
                                  'list', 'dev', wifi['ifname']],
                                 stdout=subprocess.PIPE)
            import json
            j = json.loads(ret.stdout.decode().strip())
            hwmac = j[0]['address']
        except Exception:
            pass

    return hwmac
