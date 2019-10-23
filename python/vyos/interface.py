# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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

import vyos
from vyos.config import Config
import vyos.interfaces

import re
import json

import subprocess
import time
from datetime import timedelta
import glob
from os.path import isfile
from tabulate import tabulate
from hurry.filesize import size,alternative

class Interface():

    intf = None
    intf_type = None
    valid = False

    def __init__(self,intf):
        self.intf = intf
        self.intf_type = vyos.interfaces.get_type_of_interface(self.intf)
        self.valid = (self.intf in vyos.interfaces.list_interfaces())

    def print_interface(self):

        if not self.valid:
            print("Invalid interface [{}]".format(self.intf))
            return

        if (self.intf_type == 'wireguard'):
            self.print_wireguard_interface()

        self.print_interface_stats()

    def print_interface_stats(self):
        stats = self.get_interface_stats()
        rx = [['bytes','packets','errors','dropped','overrun','mcast'],[stats['rx_bytes'],stats['rx_packets'],stats['rx_errors'],stats['rx_dropped'],stats['rx_over_errors'],stats['multicast']]]
        tx = [['bytes','packets','errors','dropped','carrier','collisions'],[stats['tx_bytes'],stats['tx_packets'],stats['tx_errors'],stats['tx_dropped'],stats['tx_carrier_errors'],stats['collisions']]]
        output = "RX: \n"
        output += tabulate(rx,headers="firstrow",numalign="right",tablefmt="plain")
        output += "\n\nTX: \n"
        output += tabulate(tx,headers="firstrow",numalign="right",tablefmt="plain")
        print('  '.join(('\n'+output.lstrip()).splitlines(True)))

    def get_interface_stats(self):
        interface_stats = dict()
        devices = [f for f in glob.glob("/sys/class/net/**/statistics")]
        for dev_path in devices:
            metrics = [f for f in glob.glob(dev_path +"/**")]
            dev = re.findall(r"/sys/class/net/(.*)/statistics",dev_path)[0]
            dev_dict = dict()
            for metric_path in metrics:
                metric = metric_path.replace(dev_path+"/","")
                if isfile(metric_path):
                    data = open(metric_path, 'r').read()[:-1]
                    dev_dict[metric] = int(data)
            interface_stats[dev] = dev_dict

        return interface_stats[self.intf]

    def print_wireguard_interface(self):
        
        wgdump = vyos.interfaces.wireguard_dump().get(self.intf,None)

        c = Config()
        c.set_level("interfaces wireguard {}".format(self.intf))
        description = c.return_effective_value("description")
        ips = c.return_effective_values("address")

        print ("interface: {}".format(self.intf))
        if (description):
            print ("  description: {}".format(description))

        if (ips):
            print ("  address: {}".format(", ".join(ips)))
        print ("  public key: {}".format(wgdump['public_key']))
        print ("  private key: (hidden)")
        print ("  listening port: {}".format(wgdump['listen_port']))
        print ()

        for peer in c.list_effective_nodes(' peer'):
            if wgdump['peers']:
                pubkey = c.return_effective_value("peer {} pubkey".format(peer))
                if pubkey in wgdump['peers']:
                    wgpeer = wgdump['peers'][pubkey] 

                    print ("  peer: {}".format(peer))
                    print ("    public key: {}".format(pubkey))

                    """ figure out if the tunnel is recently active or not """
                    status = "inactive"
                    if (wgpeer['latest_handshake'] is None):
                        """ no handshake ever """
                        status = "inactive"
                    else:
                        if int(wgpeer['latest_handshake']) > 0:
                            delta = timedelta(seconds=int(time.time() - wgpeer['latest_handshake']))
                            print ("    latest handshake: {}".format(delta))
                            if (time.time() - int(wgpeer['latest_handshake']) < (60*5)):
                                """ Five minutes and the tunnel is still active """
                                status = "active"
                            else:
                                """ it's been longer than 5 minutes """
                                status = "inactive"
                        elif int(wgpeer['latest_handshake']) == 0:
                            """ no handshake ever """
                            status = "inactive"
                        print ("    status: {}".format(status))    

                    if wgpeer['endpoint'] is not None:
                        print ("    endpoint: {}".format(wgpeer['endpoint']))

                    if wgpeer['allowed_ips'] is not None:
                        print ("    allowed ips: {}".format(",".join(wgpeer['allowed_ips']).replace(",",", ")))
                    
                    if wgpeer['transfer_rx'] > 0 or wgpeer['transfer_tx'] > 0: 
                        rx_size =size(wgpeer['transfer_rx'],system=alternative)
                        tx_size =size(wgpeer['transfer_tx'],system=alternative)
                        print ("    transfer: {} received, {} sent".format(rx_size,tx_size))

                    if wgpeer['persistent_keepalive'] is not None:
                        print ("    persistent keepalive: every {} seconds".format(wgpeer['persistent_keepalive']))
                print()
