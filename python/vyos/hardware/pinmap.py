from vyos.hardware.base import Pin
def P(default=0): return Pin(bank=0, line=0, dir='out', active_low=False, bias='none', default=default, group=None, debounce_us=0, settle_ms=0)
VARIANT = 'test'
PINS = {
    'UARTC2_SHUT_N': P(0), 'UARTC2_MODE2': P(0), 'UARTC2_MODE1': P(0), 'UARTC2_MODE0': P(0),
    'UARTC2_TERM_TX': P(0), 'UARTC2_TERM_RX': P(0), 'UARTC2_SLR': P(0),
    'CONSOLE_SHUT_N': P(0),
}
SERIAL_PORTS = {
    'UARTC2':  {'tty': '/dev/ttyS1'},
    'CONSOLE': {'tty': '/dev/ttyS0'},
}
