---
myst:
  html_meta:
    description: |
      The event handler watches the system log and runs a user-supplied
      script when a preconfigured event occurs. Configure a pattern,
      optionally a syslog identifier, and a script path per event.
    keywords: event-handler, syslog, log monitoring, script, automation
---

(event-handler)=

# Event handler

The event handler watches the system log and runs a user-supplied
script when a preconfigured event occurs. For each event, you configure
a pattern to look for in the log, optionally restrict matching to a
specific syslog identifier, and a script to run when a match occurs.

Upon a match, the event handler launches the script. The script can
read the matched log entry from an environment variable named
`message` (for example, to extract an IP address or include the log
line in a notification). You can also pass your own environment
variables or a fixed argument string to the script.

## Configuration

Each event must be configured with a name, a pattern, and a script
path. All other settings are optional.

### Mandatory settings

```{cfgcmd} set service event-handler event \<name\> filter pattern \<regex\>

**Configure a regular expression to match against log entries for the
specified event.**

The regular expression must match the entire log entry, not just a
part of it. For example, to match any log entry that contains `eth0`,
wrap it as `.*eth0.*`. Matching is case-sensitive.
```

Example:

```none
set service event-handler event LINK-DOWN filter pattern '.*eth0.*,RUNNING,.*->.*'
```

```{cfgcmd} set service event-handler event \<name\> script path \<path\>

**Configure the path to the script run for the specified event.**
```

```{note}
Event-handler scripts must be executable (see
{ref}`command-scripting`). Storing them under `/config/scripts/`
ensures they are preserved across image upgrades.
```

```{warning}
Event-handler scripts run with root privileges. Review them carefully
before use.
```

Example:

```none
set service event-handler event LINK-DOWN script path /config/scripts/link-down.py
```

### Optional settings

```{cfgcmd} set service event-handler event \<name\> filter syslog-identifier \<identifier\>

**For the specified event, match the regular expression only against
log entries produced by the specified process.**
```

Example:

```none
set service event-handler event LINK-DOWN filter syslog-identifier kernel
```

```{cfgcmd} set service event-handler event \<name\> script environment \<env-var\> value \<value\>

**Add an environment variable, with the specified name and value, to
the script's execution environment.**

Repeat the command for each variable.
```

```{note}
The variable name `message` is reserved for the matched log entry and
cannot be reused.
```

Example:

```none
set service event-handler event LINK-DOWN script environment interface_name value eth0
```

```{cfgcmd} set service event-handler event \<name\> script arguments \<arguments\>

**Append an argument string to the script invocation.**

The string is appended verbatim after the script path. To pass
multiple arguments, separate them with spaces within a single string.
```

```{note}
Prefer environment variables for passing data to the script.
```

Example:

```none
set service event-handler event LINK-DOWN script arguments '--notify admin@example.com'
```

## Example

The following example configures an event handler that reacts to
link-state messages emitted by `netplugd` for `eth0` and runs a Python
script. When triggered, the script writes a line containing the
original log entry and the configured `interface_name` value to
`/tmp/link-state.log`.

### Configuration

```none
set service event-handler event LINK-DOWN filter pattern '.*eth0.*,RUNNING,.*->.*'
set service event-handler event LINK-DOWN filter syslog-identifier 'netplugd'
set service event-handler event LINK-DOWN script environment interface_name value 'eth0'
set service event-handler event LINK-DOWN script path '/config/scripts/link-down.py'
```

### Event handler script

Save the following as `/config/scripts/link-down.py`:

```none
#!/usr/bin/env python3
#
# VyOS event-handler script example

from datetime import datetime
from os import environ
from pathlib import Path
from sys import exit

LOG_FILE = Path('/tmp/link-state.log')


def process_event() -> None:
    # 'message' is set by the event handler and holds the log entry
    # that matched the configured pattern.
    log_line = environ.get('message', '')
    # User-defined environment variables are read the same way.
    interface = environ.get('interface_name', '')

    timestamp = datetime.now().isoformat()
    with LOG_FILE.open('a') as f:
        f.write(
            f'{timestamp} link-state change on {interface}: {log_line}\n'
        )


if __name__ == '__main__':
    try:
        process_event()
        exit(0)
    except Exception as err:
        # Script stdout is discarded by the event handler, but stderr
        # is captured and surfaces in the system journal.
        from sys import stderr
        print(f'Error running script: {err}', file=stderr)
        exit(1)
```

After creating the script, make it executable:

```none
sudo chmod +x /config/scripts/link-down.py
```
