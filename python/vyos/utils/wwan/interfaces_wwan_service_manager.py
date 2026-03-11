import asyncio
from dbus_next.service import ServiceInterface, method  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from vyos.utils.wwan.interfaces_wwan_state_machine import ModemStateMachine
from vyos.utils.wwan.interfaces_wwan_config import InterfaceConfig
from vyos.utils.wwan.rfc5424_logging import RFC5424Formatter as _BaseFormatter, setup_logging


class ServiceFormatter(_BaseFormatter):
    """Service-manager-specific RFC 5424 formatter."""

    def _get_message_id(self, record):
        msg = record.getMessage().lower()
        if 'adding interface' in msg:
            return 'IFACE_ADD'
        elif 'removing interface' in msg:
            return 'IFACE_REMOVE'
        elif 'exported' in msg:
            return 'DBUS_EXPORT'
        elif 'removed' in msg:
            return 'DBUS_UNEXPORT'
        elif 'state machine' in msg:
            return 'FSM_EVENT'
        elif 'bus connection' in msg:
            return 'BUS_RECONNECT'
        elif 'error' in msg:
            return 'ERROR_EVENT'
        else:
            return 'SERVICE_EVENT'

    def _build_structured_data(self, record):
        sd_elements = []
        service_data = []
        if hasattr(record, 'interface_number'):
            service_data.append(f'interface="{record.interface_number}"')
        if hasattr(record, 'object_path'):
            service_data.append(f'path="{record.object_path}"')
        if hasattr(record, 'fsm_count'):
            service_data.append(f'fsm_count="{record.fsm_count}"')
        if service_data:
            sd_elements.append(f'[service@32473 {" ".join(service_data)}]')
        origin_data = [f'software="vyos-wwan-service"', f'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')
        return ''.join(sd_elements) if sd_elements else '-'


logger = setup_logging(__name__, "wwan-service", formatter_class=ServiceFormatter)

class ControlInterface(ServiceInterface):
    """
    Exposed at /com/igos/IgosModemManager/Control
    Allows external clients to dynamically create/delete and export
    a new InterfaceN object.
    """
    def __init__(self, manager):
        super().__init__("com.igos.IgosModemManager.Control")
        self.manager = manager

    @method()
    async def AddInterface(self, interface_number: 'i') -> 's':
        try:
            logger.info("Adding interface", extra={'interface_number': interface_number})
            await self.manager.add_interface(interface_number)
            logger.info("Interface added successfully", extra={'interface_number': interface_number})
            return f"Interface {interface_number} ready"
        except Exception as e:
            logger.error(f"Failed to add interface: {e}", extra={'interface_number': interface_number})
            raise DBusError("com.igos.IgosModemManager.Error", str(e))

    @method()
    async def RemoveInterface(self, interface_number: 'i') -> 's':
        try:
            logger.info("Removing interface", extra={'interface_number': interface_number})
            await self.manager.remove_interface(interface_number)
            logger.info("Interface removed successfully", extra={'interface_number': interface_number})
            return f"Interface {interface_number} removed"
        except Exception as e:
            logger.error(f"Failed to remove interface: {e}", extra={'interface_number': interface_number})
            raise DBusError("com.igos.IgosModemManager.Error", str(e))

class ConfigServiceManager:
    def __init__(self, bus):
        self.interface_objects = {}        # interface_number -> InterfaceConfig
        self.modem_state_machines = {}     # interface_number -> ModemStateMachine
        self.bus = bus

    async def run(self, initial_interface=None):
        await self.bus.request_name("com.igos.IgosModemManager")
        control = ControlInterface(self)
        self.bus.export("/com/igos/IgosModemManager/Control", control)

        # Auto-create initial interface if specified (non-on-demand mode)
        if initial_interface is not None:
            logger.info(f"Auto-creating interface {initial_interface} for immediate connection")
            await self.add_interface(initial_interface)
        else:
            logger.info("WWAN ConfigService is running, waiting for AddInterface() calls")

        await asyncio.get_event_loop().create_future()

    async def add_interface(self, interface_number: int):
        object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

        fsm = self.modem_state_machines.get(interface_number)
        if fsm is None:
            logger.info("Creating new state machine",
                       extra={'interface_number': interface_number})

            # Create FSM without configuration - will be set via D-Bus SetConfiguration
            fsm = ModemStateMachine(interface_number, self.bus)
            logger.info("State machine created without configuration - awaiting D-Bus SetConfiguration",
                       extra={'interface_number': interface_number})

            await fsm.initialize()

            self.modem_state_machines[interface_number] = fsm

        iface = InterfaceConfig(interface_number, fsm)
        self.bus.export(object_path, iface)
        self.interface_objects[interface_number] = iface

        logger.info("Interface exported",
                   extra={'interface_number': interface_number, 'object_path': object_path})

    async def remove_interface(self, interface_number: int):
        object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

        # Clean up configuration persistence file first
        config_iface = self.interface_objects.get(interface_number)
        if config_iface:
            try:
                config_iface._remove_configuration()
            except Exception as e:
                logger.error(f"Error removing configuration file during removal: {e}",
                           extra={'interface_number': interface_number})

        # Shutdown FSM gracefully
        fsm = self.modem_state_machines.get(interface_number)
        if fsm:
            try:
                await fsm.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down FSM during removal: {e}",
                           extra={'interface_number': interface_number})

        # Unexport the D-Bus object
        self.bus.unexport(object_path)

        # Remove from internal dictionaries
        self.interface_objects.pop(interface_number, None)
        self.modem_state_machines.pop(interface_number, None)

        logger.info("Interface removed",
                   extra={'interface_number': interface_number, 'object_path': object_path})

    async def update_bus_connection(self, new_bus):
        """Update the D-Bus connection after ModemManager restart"""
        try:
            logger.info("Updating D-Bus connection after ModemManager restart",
                       extra={'fsm_count': len(self.modem_state_machines)})

            # Update the bus reference
            old_bus = self.bus
            self.bus = new_bus

            # Re-request the bus name
            await self.bus.request_name("com.igos.IgosModemManager")

            # Re-export the control interface
            control = ControlInterface(self)
            self.bus.export("/com/igos/IgosModemManager/Control", control)

            # Re-export any existing interface objects
            for interface_number, iface in self.interface_objects.items():
                object_path = f"/com/igos/IgosModemManager/Interface{interface_number}"
                self.bus.export(object_path, iface)
                logger.info("Re-exported interface",
                           extra={'interface_number': interface_number, 'object_path': object_path})

            # Update FSM bus connections
            for interface_number, fsm in self.modem_state_machines.items():
                try:
                    await fsm.update_bus_connection(new_bus)
                except Exception as e:
                    logger.error(f"Failed to update FSM bus connection: {e}",
                               extra={'interface_number': interface_number})

            # Disconnect old bus
            if old_bus:
                old_bus.disconnect()

            logger.info("D-Bus connection updated successfully",
                       extra={'fsm_count': len(self.modem_state_machines)})

        except Exception as e:
            logger.error(f"Failed to update D-Bus connection: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown of the service manager"""
        logger.info("Shutting down ConfigServiceManager",
                   extra={'fsm_count': len(self.modem_state_machines)})

        # Stop all FSMs
        for interface_number, fsm in self.modem_state_machines.items():
            try:
                await fsm.shutdown()
                logger.info("FSM shutdown complete", extra={'interface_number': interface_number})
            except Exception as e:
                logger.error(f"Error shutting down FSM: {e}",
                           extra={'interface_number': interface_number})

        # Clear references
        self.interface_objects.clear()
        self.modem_state_machines.clear()

        logger.info("ConfigServiceManager shutdown complete")
