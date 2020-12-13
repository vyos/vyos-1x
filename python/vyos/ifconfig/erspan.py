# Copyright 2019-2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

# https://developers.redhat.com/blog/2019/05/17/an-introduction-to-linux-virtual-interfaces-tunnels/#erspan
# http://vger.kernel.org/lpc_net2018_talks/erspan-linux-presentation.pdf

from copy import deepcopy

from netaddr import EUI
from netaddr import mac_unix_expanded
from random import getrandbits

from vyos.util import dict_search
from vyos.ifconfig.interface import Interface
from vyos.validate import assert_list

@Interface.register
class _ERSpan(Interface):
    """
    _ERSpan: private base class for ERSPAN tunnels
    """
    default = {
        **Interface.default,
        **{
            'type': 'erspan',
        }
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'erspan',
            'prefixes': ['ersp',],
        },
    }
    
    options = ['local_ip','remote_ip','encapsulation','parameters']
    
    def __init__(self,ifname,**config):
        self.config = deepcopy(config) if config else {}
        super().__init__(ifname, **self.config)
    
    def change_options(self):
        pass
    
    def update(self, config):
        
        # Enable/Disable of an interface must always be done at the end of the
        # derived class to make use of the ref-counting set_admin_state()
        # function. We will only enable the interface if 'up' was called as
        # often as 'down'. This is required by some interface implementations
        # as certain parameters can only be changed when the interface is
        # in admin-down state. This ensures the link does not flap during
        # reconfiguration.
        super().update(config)
        state = 'down' if 'disable' in config else 'up'
        self.set_admin_state(state)
    
    def _create(self):
        pass

class ERSpanIf(_ERSpan):
    """
    ERSpanIf: private base class for ERSPAN Over GRE and IPv4 tunnels
    """
    
    def _create(self):
        ifname = self.config['ifname']
        local_ip = self.config['local_ip']
        remote_ip = self.config['remote_ip']
        key = self.config['parameters']['ip']['key']
        version = self.config['parameters']['version']
        command = f'ip link add dev {ifname} type erspan local {local_ip} remote {remote_ip} seq key {key} erspan_ver {version}'
        
        if int(version) == 1:
            idx=dict_search('parameters.erspan.idx',self.config)
            if idx:
                command += f' erspan {idx}'
        elif int(version) == 2:
            direction=dict_search('parameters.erspan.direction',self.config)
            if direction:
                command += f' erspan_dir {direction}'
            hwid=dict_search('parameters.erspan.hwid',self.config)
            if hwid:
                command += f' erspan_hwid {hwid}'
        
        ttl = dict_search('parameters.ip.ttl',self.config)
        if ttl:
            command += f' ttl {ttl}'
        tos = dict_search('parameters.ip.tos',self.config)
        if tos:
            command += f' tos {tos}'
                
        self._cmd(command)
    
    def change_options(self):
        ifname = self.config['ifname']
        local_ip = self.config['local_ip']
        remote_ip = self.config['remote_ip']
        key = self.config['parameters']['ip']['key']
        version = self.config['parameters']['version']
        command = f'ip link set dev {ifname} type erspan local {local_ip} remote {remote_ip} seq key {key} erspan_ver {version}'
        
        if int(version) == 1:
            idx=dict_search('parameters.erspan.idx',self.config)
            if idx:
                command += f' erspan {idx}'
        elif int(version) == 2:
            direction=dict_search('parameters.erspan.direction',self.config)
            if direction:
                command += f' erspan_dir {direction}'
            hwid=dict_search('parameters.erspan.hwid',self.config)
            if hwid:
                command += f' erspan_hwid {hwid}'
        
        ttl = dict_search('parameters.ip.ttl',self.config)
        if ttl:
            command += f' ttl {ttl}'
        tos = dict_search('parameters.ip.tos',self.config)
        if tos:
            command += f' tos {tos}'
                
        self._cmd(command)

class ER6SpanIf(_ERSpan):
    """
    ER6SpanIf: private base class for ERSPAN Over GRE and IPv6 tunnels
    """
    
    def _create(self):
        ifname = self.config['ifname']
        local_ip = self.config['local_ip']
        remote_ip = self.config['remote_ip']
        key = self.config['parameters']['ip']['key']
        version = self.config['parameters']['version']
        command = f'ip link add dev {ifname} type ip6erspan local {local_ip} remote {remote_ip} seq key {key} erspan_ver {version}'
        
        if int(version) == 1:
            idx=dict_search('parameters.erspan.idx',self.config)
            if idx:
                command += f' erspan {idx}'
        elif int(version) == 2:
            direction=dict_search('parameters.erspan.direction',self.config)
            if direction:
                command += f' erspan_dir {direction}'
            hwid=dict_search('parameters.erspan.hwid',self.config)
            if hwid:
                command += f' erspan_hwid {hwid}'
        
        ttl = dict_search('parameters.ip.ttl',self.config)
        if ttl:
            command += f' ttl {ttl}'
        tos = dict_search('parameters.ip.tos',self.config)
        if tos:
            command += f' tos {tos}'
                
        self._cmd(command)
    
    def change_options(self):
        ifname = self.config['ifname']
        local_ip = self.config['local_ip']
        remote_ip = self.config['remote_ip']
        key = self.config['parameters']['ip']['key']
        version = self.config['parameters']['version']
        command = f'ip link set dev {ifname} type ip6erspan local {local_ip} remote {remote_ip} seq key {key} erspan_ver {version}'
        
        if int(version) == 1:
            idx=dict_search('parameters.erspan.idx',self.config)
            if idx:
                command += f' erspan {idx}'
        elif int(version) == 2:
            direction=dict_search('parameters.erspan.direction',self.config)
            if direction:
                command += f' erspan_dir {direction}'
            hwid=dict_search('parameters.erspan.hwid',self.config)
            if hwid:
                command += f' erspan_hwid {hwid}'
                
        self._cmd(command)
