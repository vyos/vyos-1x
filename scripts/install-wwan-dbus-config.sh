#!/bin/bash
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

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBUS_CONFIG_SRC="${SCRIPT_DIR}/../src/etc/dbus-1/system.d/com.igos.IgosModemManager.conf"
SYSTEMD_SERVICE_SRC="${SCRIPT_DIR}/../src/etc/systemd/system/igos-wwan-manager.service"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "Installing VyOS WWAN Manager D-Bus and systemd configuration..."

# Create D-Bus system configuration directory if it doesn't exist
mkdir -p /etc/dbus-1/system.d

# Install D-Bus policy file
echo "Installing D-Bus policy file..."
cp "${DBUS_CONFIG_SRC}" /etc/dbus-1/system.d/
chmod 644 /etc/dbus-1/system.d/com.igos.IgosModemManager.conf
chown root:root /etc/dbus-1/system.d/com.igos.IgosModemManager.conf

# Install systemd service file
echo "Installing systemd service file..."
cp "${SYSTEMD_SERVICE_SRC}" /etc/systemd/system/
chmod 644 /etc/systemd/system/igos-wwan-manager.service
chown root:root /etc/systemd/system/igos-wwan-manager.service

# Reload D-Bus configuration
echo "Reloading D-Bus configuration..."
systemctl reload dbus

# Reload systemd daemon
echo "Reloading systemd configuration..."
systemctl daemon-reload

# Make sure the WWAN main script is executable
WWAN_MAIN_SCRIPT="/usr/lib/python3/dist-packages/vyos/utils/wwan/interfaces_wwan_main.py"
if [ -f "${WWAN_MAIN_SCRIPT}" ]; then
    chmod +x "${WWAN_MAIN_SCRIPT}"
    echo "Made WWAN main script executable: ${WWAN_MAIN_SCRIPT}"
else
    echo "Warning: WWAN main script not found at ${WWAN_MAIN_SCRIPT}"
    echo "Make sure to install the VyOS WWAN package first, or update the path in the systemd service file."
fi

echo ""
echo "Installation complete! You can now:"
echo ""
echo "1. Test the WWAN manager manually:"
echo "   sudo python3 /usr/lib/python3/dist-packages/vyos/utils/wwan/interfaces_wwan_main.py --interface 0"
echo ""
echo "2. Or enable and start the systemd service:"
echo "   sudo systemctl enable igos-wwan-manager.service"
echo "   sudo systemctl start igos-wwan-manager.service"
echo ""
echo "3. Check service status:"
echo "   sudo systemctl status igos-wwan-manager.service"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u igos-wwan-manager.service -f"
echo ""

# Optional: Test D-Bus policy by attempting a quick connection test
echo "Testing D-Bus configuration..."
if timeout 10s busctl --system list | grep -q "com.igos.IgosModemManager" 2>/dev/null; then
    echo "✓ IgosModemManager service is available on D-Bus"
else
    echo "ℹ IgosModemManager service not currently running (this is expected until you start it)"
fi

echo ""
echo "Configuration files installed successfully!"
echo ""
echo "Note: If you continue to see D-Bus permission errors, you may need to:"
echo "1. Restart the D-Bus service: sudo systemctl restart dbus"
echo "2. Or reboot the system to ensure all changes take effect"
echo ""
