# VyOS Smoketests

A brief overview of the smoketesting platform

## CLI set/delete and validation

Smoketests execute predefined VyOS CLI commands and verify that the
corresponding daemon is running and/or service configuration is correctly
rendered.

Smoketests are available for the system (e.g. Kernel) and the CLI. They can
be run manually by simply executing the Python script on a live VyOS system.

```
vyos@vyos:~$ /usr/libexec/vyos/tests/smoke/cli/test_protocols_bgp.py
test_bgp_01_simple (__main__.TestProtocolsBGP) ... ok
test_bgp_02_neighbors (__main__.TestProtocolsBGP) ... ok
...
test_bgp_13_solo (__main__.TestProtocolsBGP) ... ok

----------------------------------------------------------------------
Ran 13 tests in 348.191s

OK
```

It is possible to only execute a single testcase

```
vyos@vyos:~$ /usr/libexec/vyos/tests/smoke/cli/test_protocols_bgp.py -k test_bgp_02_neighbors
test_bgp_02_neighbors (__main__.TestProtocolsBGP) ... ok

----------------------------------------------------------------------
Ran 1 test in 6.872s

OK
```

## Configuration Migration

The files in `smoketests/configs/` are real VyOS configurations taken from
production or lab systems. They provide realistic inputs to test configuration
migration and ensure that existing configs still load correctly after code
changes.

Example:

After assembling a VyOS ISO image from vyos-build repository, a `make testc`
loads the configuration files and its associated CLI commands that are asserted.
After loading the configuration and executing any necessary migration scripts,
we then check whether the resulting `show configuration commands` output
contains all commands listed in `smoketests/configs/assert`. If all listed
commands are present, the test passes.

Each config file has exactly one matching expected-set file inside the
`smoketests/configs/assert` folder.

When modifying or adding a migration script, update the matching file in
`smoketests/configs/assert` to reflect any new or changed CLI commands.

**NOTE:** The migrated output does not need to match exactly. Missing lines in
the assert file are not treated as failures. A test only fails when a listed
line differs from the actual migrated output.

```
smoketests/
  ├── configs/               # Input configuration files
  │     ├── assert/          # Expected CLI commands after migration
  │     │     ├── example1
  │     │     ├── example2
  │     │     └── ...
  │     ├── no-load/         # Large configurations we do not automatically test
  │     │     └── ...
  │     ├── example1
  │     ├── example2
  │     └── ...
  └── README.md              # Documentation for adding and running tests
```


