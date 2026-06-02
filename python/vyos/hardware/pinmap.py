# Copyright (C) 2024-2026 Perle Systems Limited
# SPDX-License-Identifier: GPL-2.0-or-later
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

from vyos.hardware.base import Pin
def P(default=0): return Pin(bank=0, line=0, dir='out', active_low=False, bias='none', default=default, group=None, debounce_us=0, settle_ms=0)
VARIANT = 'test'

# AM64x SoC UART ↔ /dev/ttyS<N> mapping (per board .dts aliases):
#   ttyS0  -> console UART (MAIN_UART0)
#   ttyS1  -> MAIN_UART1   (UARTC0 transceiver, front-panel)
#   ttyS2  -> MAIN_UART2   (UARTC2 transceiver, front-panel)
#   ttyS3  -> MAIN_UART4   (UARTC4 transceiver, front-panel)
#   ttyS4  -> MAIN_UART5   (UARTC5 transceiver, front-panel)
# These numbers are derived by the kernel from the device-tree `serial<N>`
# aliases; a tty *path* in SERIAL_PORTS below is a CLAIM that the real
# hardware overlay (`igos-am64x-*`) verifies at boot via dt_node.

PINS = {
    'UARTC0_SHUT_N': P(0),  'UARTC0_TERM_TX': P(0), 'UARTC0_TERM_RX': P(0),
    'UARTC2_SHUT_N': P(0),  'UARTC2_MODE2':   P(0), 'UARTC2_MODE1':   P(0),
    'UARTC2_MODE0':  P(0),  'UARTC2_TERM_TX': P(0), 'UARTC2_TERM_RX': P(0),
    'UARTC2_SLR':    P(0),
    'UARTC4_SHUT_N': P(0),  'UARTC4_MODE2':   P(0), 'UARTC4_MODE1':   P(0),
    'UARTC4_MODE0':  P(0),  'UARTC4_TERM_TX': P(0), 'UARTC4_TERM_RX': P(0),
    'UARTC4_SLR':    P(0),
    'UARTC5_SHUT_N': P(0),  'UARTC5_MODE2':   P(0), 'UARTC5_MODE1':   P(0),
    'UARTC5_MODE0':  P(0),  'UARTC5_TERM_TX': P(0), 'UARTC5_TERM_RX': P(0),
    'UARTC5_SLR':    P(0),
    'CONSOLE_SHUT_N': P(0),
}

# AM64x SoC UART base addresses (from the TRM / k3-am64-main.dtsi):
#   MAIN_UART0 = 0x02800000   (console, ttyS0)
#   MAIN_UART1 = 0x02810000   (ttyS1, UARTC0)
#   MAIN_UART2 = 0x02820000   (ttyS2, UARTC2)
#   MAIN_UART4 = 0x02840000   (ttyS3, UARTC4)
#   MAIN_UART5 = 0x02850000   (ttyS4, UARTC5)
# dt_node is matched as a suffix of /sys/class/tty/<N>/device/of_node's
# realpath, so the leaf '/bus@f4000/serial@<addr>' is enough.
SERIAL_PORTS = {
    'CONSOLE': {'tty': '/dev/ttyS0',
                'dt_node': '/bus@f4000/serial@2800000'},
    'UARTC0':  {'tty': '/dev/ttyS1',
                'dt_node': '/bus@f4000/serial@2810000',
                'type': 'fixed_rs232'},
    'UARTC2':  {'tty': '/dev/ttyS2',
                'dt_node': '/bus@f4000/serial@2820000'},
    'UARTC4':  {'tty': '/dev/ttyS3',
                'dt_node': '/bus@f4000/serial@2840000'},
    'UARTC5':  {'tty': '/dev/ttyS4',
                'dt_node': '/bus@f4000/serial@2850000'},
}
