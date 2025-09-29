libvyosconfig
=============

This library mixes the multiway tree manipulation libraries from [vyconf](https://github.com/vyos/vyconf)
with a parser and a formatter for VyOS 1.x config format, and is meant to be used in config migration scripts
and analysis/conversion tools.

The main purpose is to provide bindings for Python, so using this library directly from C is strongly
discouraged: not just the interface is not guaranteed to be stable, it's written to be a bridge between
two high level languages so it would be very inconvenient to use from C.

## Building

You need to install OPAM and then use it to install OCaml (4.08 or later, latest 4.12 works fine).


```
# Clone and install the vyos1x-config library
git clone https://github.com/vyos/vyos1x-config
opam pin add vyos1x-config .

# Install build deps
opam install ctypes ctypes-foreign ctypes-build

# Build the Debian package
dpkg-buildpackage -b -us -uc -tc
```
