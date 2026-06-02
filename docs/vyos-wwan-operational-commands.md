# IGOS WWAN Enhanced Interface — Operational Command Reference

This document defines the IGOS operational-mode commands implemented for the
enhanced WWAN interface management service.  All data is sourced from the
WWAN FSM D-Bus service (no raw QMI/mmcli calls from op-mode scripts, avoiding
conflicts with ModemManager).

For the configuration (`set`) commands, see `vyos-wwan-set-commands.md`.

---

## Command Tree

```
show
  └── interfaces
        └── wwan                                           # summary of all WWAN interfaces
              ├── detail                                    # detailed info for all WWAN interfaces
              └── <wwanN>                                   # summary for specific interface
                    ├── detail                              # full detail (all sections combined)
                    ├── hardware                            # modem hardware info
                    ├── signal                              # RF signal metrics
                    ├── sim                                 # SIM/slot/PIN information
                    ├── status                              # connection state and IP config
                    ├── wait-failover-alert                 # wait for next failover alert
                    │     └── timeout <1-600>               # override wait timeout (seconds)
                    ├── monitor-alerts                      # collect live alerts for a timeout window
                    │     ├── timeout <1-600>               # monitor duration in seconds
                    │     ├── severity {info|warning|critical}
                    │     └── category {connectivity|sim|usage}
                    ├── sms                                 # list all SMS messages
                    │     ├── <id>                          # read specific SMS message (preferred)
                    │     └── message <id>                  # read specific SMS message
                    └── event-log                           # network event log (journalctl)
                          ├── route                         # route events only
                          ├── link                          # link events only
                          ├── addr                          # address events only
                          ├── neigh                         # neighbor table events only
                          └── rule                          # PBR rule events only

connect
  └── interface <wwanN>                                    # bring up WWAN bearer

disconnect
  └── interface <wwanN>                                    # tear down WWAN bearer

generate
  └── interfaces
        └── wwan <wwanN>
              └── sms
                    └── number <phone>
                          └── message <text>              # send SMS

clear
  └── interfaces
        └── wwan <wwanN>
              └── sms                                      # clear all SMS messages
                    └── message <id>                       # clear specific SMS message
```

---

## Show Commands

### `show interfaces wwan`

Summary of all WWAN interfaces (standard IGOS interface listing).

```
igos@igos:~$ show interfaces wwan
```

**Script:** `interfaces.py show_summary --intf-type=wwan`

Displays the standard interface summary table (admin/link state, IPv4/IPv6
addresses, description) for every `wwan*` interface.

---

### `show interfaces wwan detail`

Detailed standard interface information for all WWAN interfaces.

```
igos@igos:~$ show interfaces wwan detail
```

**Script:** `interfaces.py show --intf-type=wwan`

Standard IGOS detailed interface output (counters, MTU, MAC, etc.) for every
`wwan*` interface.

---

### `show interfaces wwan <wwanN>`

Standard interface summary for a specific WWAN interface.

```
igos@igos:~$ show interfaces wwan wwan0
```

**Script:** `interfaces.py show --intf-name="$4" --intf-type=wirelessmodem`

---

### `show interfaces wwan <wwanN> status`

Current connection state, IP configuration, signal overview, SMS count, and
live bearer session data usage.

```
igos@igos:~$ show interfaces wwan wwan0 status
```

**Script:** `show_wwan.py show_status --interface="$4"`

**Output fields:**

| Section | Field | Description |
|---|---|---|
| **Connection** | State | FSM state (e.g. `CONNECTED`, `REGISTERED`, `FAILED`) |
| | Connection mode | `always-on`, `connect-on-demand`, `dial-on-demand` |
| | Power state | Modem power state (e.g. `on`, `low`, `off`) |
| | Access technology | Active RAT (e.g. `lte`, `5gnr`, `umts`) |
| | Operator | Network operator name |
| | Operator code | MCC/MNC code |
| | APN | Connected APN name |
| | Log level | Effective WWAN log level |
| | Log sink | Effective WWAN log destination (`both`, `journal`, `syslog`) |
| | Failure reason | Set when state is `FAILED` |
| **IP Configuration** | IPv4 address | Bearer IPv4 address |
| | IPv4 gateway | IPv4 default gateway |
| | IPv4 DNS | IPv4 DNS server(s) |
| | IPv6 address | Bearer IPv6 address |
| | IPv6 gateway | IPv6 default gateway |
| | IPv6 DNS | IPv6 DNS server(s) |
| | MTU | Effective MTU (carrier-negotiated or fallback) |
| **Signal** | Quality | Signal quality as percentage |
| | Strength | Signal strength in dBm |
| | Active bands | Currently active radio bands |
| **SMS** | SMS supported | Whether modem supports SMS |
| | Messages | Total SMS message count |
| | Unread | Unread incoming SMS count |
| **Data Usage (session)** | RX bytes | Bytes received on the current bearer session |
| | TX bytes | Bytes transmitted on the current bearer session |
| | Duration | Current bearer session duration (hours/minutes/seconds) |

**JSON mode:** `show interfaces wwan wwan0 status --raw`

---

### `show interfaces wwan <wwanN> hardware`

Modem hardware identification.

```
igos@igos:~$ show interfaces wwan wwan0 hardware
```

**Script:** `show_wwan.py show_hardware --interface="$4"`

**Output fields:**

| Field | Description |
|---|---|
| Manufacturer | Modem manufacturer (e.g. `Quectel`) |
| Model | Modem model (e.g. `RM520N-GL`) |
| IMEI | International Mobile Equipment Identity |
| Firmware revision | Modem firmware version string |
| Hardware revision | Modem hardware revision |
| Phone number | Primary MSISDN |
| All numbers | All MSISDNs (shown when more than one) |
| Device path | ModemManager device path |
| Power state | Current modem power state |

**JSON mode:** `show interfaces wwan wwan0 hardware --raw`

---

### `show interfaces wwan <wwanN> signal`

RF signal metrics and active radio bands.

```
igos@igos:~$ show interfaces wwan wwan0 signal
```

**Script:** `show_wwan.py show_signal --interface="$4"`

**Output fields:**

| Section | Field | Description |
|---|---|---|
| **Summary** | Quality | Signal quality percentage (0–100%) |
| | Strength | Signal strength in dBm |
| | Technology | Active radio technology (e.g. `lte`, `5gnr`) |
| **Detailed Metrics** | RSSI | Received Signal Strength Indicator (dBm) |
| | RSRP | Reference Signal Received Power (dBm) — LTE/5G |
| | RSRQ | Reference Signal Received Quality (dB) — LTE/5G |
| | SNR | Signal-to-Noise Ratio (dB) |
| **Active Bands** | *(list)* | Currently active radio bands (e.g. `eutran-7`, `ngran-78`) |

**Signal quality interpretation:**

| RSRP (dBm) | Quality | Description |
|---|---|---|
| ≥ −80 | Excellent | Strong signal |
| −80 to −90 | Good | Reliable connection |
| −90 to −100 | Fair | May experience reduced throughput |
| −100 to −110 | Poor | Connection instability likely |
| < −110 | Very poor | Frequent disconnections expected |

**JSON mode:** `show interfaces wwan wwan0 signal --raw`

---

### `show interfaces wwan <wwanN> sim`

SIM card, slot, failover, and PIN/PUK status.

```
igos@igos:~$ show interfaces wwan wwan0 sim
```

**Script:** `show_wwan.py show_sim --interface="$4"`

**Output fields:**

| Section | Field | Description |
|---|---|---|
| **Active SIM** | Active slot | Currently active SIM slot number |
| | Configured slot | Primary slot from configuration |
| | On configured SIM | `yes` if active slot matches configured primary |
| | On failover SIM | `yes` if active SIM is the failover (backup) |
| | Switch reason | Why the SIM was switched (e.g. signal loss, connect failure, data limit) |
| | IMSI | International Mobile Subscriber Identity |
| | ICCID | Integrated Circuit Card ID |
| | Operator | Network operator name |
| | SPN | Service Provider Name |
| | MCC/MNC | Mobile Country Code / Mobile Network Code |
| **Failover** | Failover enabled | Whether automatic SIM failover is on |
| | Failback enabled | Whether automatic failback to primary is on |
| **PIN/PUK Status** | Status | `ok`, `FAILED`, or `PERMANENTLY LOCKED` |
| | PIN unlock | `ok` or `FAILED` |
| | PUK unlock | `ok` or `FAILED` |
| | PIN retries | Remaining PIN entry attempts |
| | PUK retries | Remaining PUK entry attempts |
| **Slot N** *(per slot)* | Present | Whether a SIM is physically inserted |
| | Enabled | Whether the slot is administratively enabled |
| | IMSI | SIM's IMSI |
| | ICCID | SIM's ICCID |
| | Operator | SIM's home operator |

**JSON mode:** `show interfaces wwan wwan0 sim --raw`

---

### `show interfaces wwan <wwanN> detail`

Comprehensive display combining all sections: status, hardware, SIM, signal,
plus billing-cycle cumulative usage, runtime bearer/recovery counters,
failover history, and configuration summary.

```
igos@igos:~$ show interfaces wwan wwan0 detail
```

**Script:** `show_wwan.py show_detail --interface="$4"`

**Additional fields** (beyond the sections above):

| Section | Field | Description |
|---|---|---|
| **Cumulative Data Usage** | Cumulative bytes | Total bytes across all sessions in current billing cycle |
| | Including session | Cumulative + current session bytes |
| | Billing day | Day of month on which the billing-cycle counters reset |
| | Tracked slot | Active slot associated with the persisted usage record |
| | Tracked ICCID | Physical SIM ICCID used for billing usage tracking when available; falls back to slot-based tracking if unavailable |
| | Data limit | Configured data limit in bytes (if set) |
| | Usage | Percentage of data limit consumed |
| | Limit action | Action when limit reached (`none`, `disable`, `sim-failover`, `sim-failover-sticky`) |
| **Failover History** | Failover count | Number of SIM failover events |
| | Last failover | Timestamp of last failover |
| | Recovery attempts | Number of connectivity recovery attempts |
| **Runtime Counters** | Bearer drops | Number of bearer-down events since boot |
| | Registration losses | Number of bearer losses that surfaced as registration-only state since boot |
| | Reconnect attempts | Automatic reconnection attempts since boot |
| | Reconnect successes | Successful bearer recoveries since boot |
| | SIM switches | Runtime SIM slot changes since boot |
| | Total downtime | Accumulated bearer downtime since boot |
| | Current downtime | Current bearer downtime if the interface is presently disconnected |
| | Last disconnect | Timestamp of the last bearer-down event |
| | Last reason | Reason recorded for the last bearer-down event |
| **Configuration** | Network mode | Configured RAT selection mode |
| | Reconnection | Enhanced reconnection status |
| | Monitoring | Connectivity monitoring status |
| | Interface mgmt | Interface management status |
| | Log level | Effective WWAN log level |
| | Log sink | Effective WWAN log destination (`both`, `journal`, `syslog`) |
| | Verbose logging | Verbose logging status |

**JSON mode:** `show interfaces wwan wwan0 detail --raw` (returns the full FSM status dict)

---

### `show interfaces wwan <wwanN> wait-failover-alert`

Wait for the next failover-related alert for the specified interface.

```
igos@igos:~$ show interfaces wwan wwan0 wait-failover-alert
```

Optional timeout override:

```
igos@igos:~$ show interfaces wwan wwan0 wait-failover-alert timeout 300
```

**Script:** `show_wwan.py show_wait_failover --interface="$4"`

**Behavior:**
- Uses `WWANClientSync.wait_for_failover_alert()` (AlertBus-backed helper)
- Waits for a new failover/switch alert (default timeout: 120 seconds)
- Timeout can be tuned via `timeout <1-600>`
- Prints a structured alert block when received
- Prints timeout notice if no failover alert arrives in time

**JSON mode:** `show interfaces wwan wwan0 wait-failover-alert --raw`

---

### `show interfaces wwan <wwanN> monitor-alerts`

Collect matching live alerts from AlertBus over a fixed monitoring window.

```
igos@igos:~$ show interfaces wwan wwan0 monitor-alerts
```

Optional filters:

```
igos@igos:~$ show interfaces wwan wwan0 monitor-alerts timeout 120
igos@igos:~$ show interfaces wwan wwan0 monitor-alerts severity critical
igos@igos:~$ show interfaces wwan wwan0 monitor-alerts category connectivity
```

**Script:** `show_wwan.py show_monitor_alerts --interface="$4"`

**Behavior:**
- Uses `WWANClientSync.monitor_alerts()` (AlertBus signal subscription)
- Collects matching alerts during timeout window (default: 30s)
- Optional server-side filter on `severity` and `category`
- Returns count + per-alert summary (sequence, timestamp, code/type/category/message)

**JSON mode:** `show interfaces wwan wwan0 monitor-alerts --raw`

---

### `show interfaces wwan <wwanN> sms`

List all SMS messages for the active SIM.

```
igos@igos:~$ show interfaces wwan wwan0 sms
```

**Script:** `wwan_sms.py show_sms --interface="$4"`

**Output:** Tabular list with columns:

| Column | Description |
|---|---|
| ID | Message ID (numeric) |
| Direction | `<-` incoming, `->` outgoing |
| Number | Phone number |
| Timestamp | Date/time (first 19 characters) |
| Message | Text (truncated to 50 chars in list view) |
| Flag | `[NEW]` appended for unread incoming messages |

**JSON mode:** `show interfaces wwan wwan0 sms --raw` (returns array of message dicts)

---

### `show interfaces wwan <wwanN> sms <id>`

Read a specific SMS message by ID. Incoming messages are marked as read.

```
igos@igos:~$ show interfaces wwan wwan0 sms 3
```

**Script:** `wwan_sms.py show_sms_message --interface="$4" --message-id="$6"`

**JSON mode:** `show interfaces wwan wwan0 sms 3 --raw`

---

### `show interfaces wwan <wwanN> sms message <id>`

Alternate syntax for reading a specific SMS message by ID.

```
igos@igos:~$ show interfaces wwan wwan0 sms message 3
```

**Script:** `wwan_sms.py show_sms_message --interface="$4" --message-id="$7"`

**Output fields:**

| Field | Description |
|---|---|
| ID | Message ID |
| Direction | `incoming` or `outgoing` |
| Number | Phone number |
| Timestamp | Full date/time |
| Status | Message delivery status |
| Read | `yes` / `no` (incoming only) |
| *(text)* | Full message body |

**JSON mode:** `show interfaces wwan wwan0 sms message 3 --raw`

---

### `show interfaces wwan <wwanN> event-log`

Show network event log entries for the specified WWAN interface (link, address,
route, neighbor, and PBR rule events from journalctl).

```
igos@igos:~$ show interfaces wwan wwan0 event-log
```

**Sub-commands:**

| Command | Description |
|---|---|
| `event-log` | All event types for the interface |
| `event-log route` | Route change events only |
| `event-log link` | Link state events only |
| `event-log addr` | Address add/remove events only |
| `event-log neigh` | Neighbor table events only |
| `event-log rule` | PBR rule change events only |

**Source:** `journalctl --no-hostname --boot --unit vyos-network-event-logger.service`

---

## Connect / Disconnect Commands

### `connect interface <wwanN>`

Bring up (or re-establish) the WWAN bearer connection.

```
igos@igos:~$ connect interface wwan0
```

**Script:** `connect_disconnect.py --connect --interface "$3"`

**Behaviour:**
- If already connected: prints `Interface wwan0: already connected!`
- If not connected: re-applies the interface configuration via `interfaces_wwan.py`,
  which causes the FSM to initiate the connection sequence
- After connection, QoS policy is re-applied if configured

> **Note:** In `connect-on-demand` and `dial-on-demand` modes, the
> `connect_bearer()` D-Bus method can also be used programmatically.

---

### `disconnect interface <wwanN>`

Tear down the WWAN bearer connection.

```
igos@igos:~$ disconnect interface wwan0
```

**Script:** `connect_disconnect.py --disconnect --interface "$3"`

**Behaviour:**
- If already disconnected: prints `Interface wwan0: connection is already down`
- If connected: issues `mmcli --modem N --simple-disconnect` to tear down the bearer

> **Note:** In `connect-on-demand` and `dial-on-demand` modes, the
> `disconnect_bearer()` D-Bus method can also be used programmatically.
> In those modes, the bearer is released but the modem stays registered
> on the network (SMS available, no data).

---

## SMS Commands

### `generate interfaces wwan <wwanN> sms number <phone> message <text>`

Send an SMS message via the WWAN modem.

```
igos@igos:~$ generate interfaces wwan wwan0 sms number '+15551234567' message 'Router rebooted successfully'
```

**Script:** `wwan_sms.py send_sms --interface="$4" --number="$7" --message="$9"`

> **Phone number format:** Use E.164 format (`+<countrycode><subscriber>`,
> for example `+14168310352`) for best interoperability. Non-E.164 formats
> may work on some modem/carrier combinations but are not guaranteed.

**Output:**
- Human: `SMS sent to +15551234567 (message id: 42)`
- JSON (`--raw`): `{"message_id": 42}`

**Tab completion:** WWAN interface names are auto-completed from `/sys/class/net/wwan*`.

> **Note:** SMS is available whenever the modem is registered on the network,
> even in `connect-on-demand` mode when the bearer is not established.

---

### `clear interfaces wwan <wwanN> sms`

Delete all SMS messages on the active SIM.

```
igos@igos:~$ clear interfaces wwan wwan0 sms
```

**Script:** `wwan_sms.py delete_all_sms --interface="$4"`

**Output:**
- Human: `All SMS messages deleted`
- JSON (`--raw`): `{"status": "ok"}`

---

### `clear interfaces wwan <wwanN> sms message <id>`

Delete a specific SMS message by ID.

```
igos@igos:~$ clear interfaces wwan wwan0 sms message 3
```

**Script:** `wwan_sms.py delete_sms --interface="$4" --message-id="$7"`

**Output:**
- Human: `SMS message 3 deleted`
- JSON (`--raw`): `{"status": "ok"}`

**Tab completion:** Message IDs accept values 1–999.

---

## D-Bus Service Interface

All operational commands flow through the WWAN FSM D-Bus service.  Op-mode
scripts use the `WWANClientSync` client library from
`python/vyos/utils/wwan/wwan_client.py`.

### D-Bus Object Paths

| Path | Interface | Purpose |
|---|---|---|
| `/com/igos/IgosModemManager/Control` | `com.igos.IgosModemManager.Control` | Service management (add/remove interfaces) |
| `/com/igos/IgosModemManager/Interface<N>` | `com.igos.IgosModemManager.Interface` | Per-interface operations |
| `/com/igos/IgosModemManager/AlertBus` | `com.igos.IgosModemManager.AlertBus` | Structured WWAN alert stream + recent-alert history |

### Per-Interface D-Bus Methods

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `get_status()` | — | Full status dict | All status fields (used by all `show` commands) |
| `get_bearer_status()` | — | `"connected"` / `"disconnected"` | Quick bearer state check |
| `connect()` | — | `"accepted"` | Initiate bearer connection |
| `disconnect()` | — | `"accepted"` | Terminate bearer connection |
| `connect_bearer()` | — | `"accepted"` | Establish data bearer (on-demand modes) |
| `disconnect_bearer()` | — | `"accepted"` | Release data bearer (on-demand modes) |
| `send_sms(recipient, message)` | number, text | `{"message_id": N}` | Send SMS |
| `list_sms()` | — | Array of message dicts | List all SMS messages |
| `read_sms(message_id)` | integer | Message dict | Read specific SMS (marks as read) |
| `delete_sms(message_id)` | integer | `{"status": "ok"}` | Delete specific SMS |
| `delete_all_sms()` | — | `{"status": "ok"}` | Delete all SMS for active SIM |

### Control D-Bus Methods

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `AddInterface(interface_number)` | integer | — | Create and export new interface handler |
| `RemoveInterface(interface_number)` | — | — | Shutdown and unexport interface |

### AlertBus D-Bus Methods and Signal

| Name | Parameters | Returns | Description |
|---|---|---|---|
| `Alert` (signal) | `payload` (`a{sv}`) | — | Emitted for normalized WWAN alerts (bearer down/up, failover, data-limit, FSM failure) |
| `AlertRaised` (signal) | `alert_json` (`s`) | — | Compatibility signal carrying the same alert envelope as compact JSON |
| `GetRecentAlerts(limit, interface_number)` | integer, integer (`-1` = all) | Array of alert dicts | Retrieve recent alerts from in-memory ring buffer |
| `AckAlert(alert_id)` | string | boolean | Mark an alert as acknowledged (`state=acked`) |
| `ClearAlerts(interface_number)` | integer (`-1` = all) | Status string | Clear alert history globally or per-interface |

### WWAN client subscription helpers

The WWAN Python client library includes callback and monitor helpers:

- `WWANClient.subscribe_alerts(callback, ...) -> subscription_id`
- `WWANClient.unsubscribe_alerts(subscription_id) -> bool`
- `WWANClient.monitor_alerts(timeout=..., ...) -> list[alert]`
- `WWANClientSync.monitor_alerts(...) -> list[alert]`

These helpers are the base for protocol adapters (SNMP/REST/MQTT) without
coupling protocol-specific code into the WWAN FSM.

### Protocol adapter skeletons (SNMP/REST/MQTT)

The module `python/vyos/utils/wwan/alert_adapters.py` provides decoupled
subscriber skeletons:

- `AlertSubscriptionRunner` — shared subscriber dispatcher
- `RestAlertAdapter` — in-memory recent/active alert store for REST endpoints
- `MqttAlertAdapter` — topic mapping to `igos/alerts/<category>/<source>`
- `SnmpAlertAdapter` — stable `code -> OID` trap mapping via callback

Adapters are transport-agnostic by design:
- MQTT uses injected `publish_func(topic, payload, qos, retain)`
- SNMP uses injected `send_trap_func(oid, varbinds)`

This keeps WWAN core stable while protocol-specific implementations evolve in
separate daemons/services.

### Alert envelope schema (stable contract)

All AlertBus payloads use a normalized envelope with stable machine fields:

| Field | Type | Description |
|---|---|---|
| `id` | string (UUID) | Unique alert id |
| `timestamp` | string (UTC ISO8601) | Alert creation time |
| `sequence` | integer | Monotonic sequence number |
| `severity` | string | `info` \| `warning` \| `critical` |
| `category` | string | `connectivity` \| `sim` \| `usage` |
| `source` | string | Source component (e.g. `wwan-fsm`) |
| `code` | string | Stable machine code (e.g. `WWAN_BEARER_DOWN`) |
| `message` | string | Human-readable message |
| `labels` | dict | Structured tags (interface, fsm_state, etc.) |
| `state` | string | `open` \| `cleared` \| `acked` |
| `dedupe_key` | string | Stable dedupe/suppression key |
| `interface_number` | integer | Interface index (`-1` = global/service) |

### AlertBus → Journald bridge (for standard IGOS `service event-handler`)

AlertBus events are also written to journald with:

- `SYSLOG_IDENTIFIER=igos-wwan-alertbus`
- `MESSAGE=<alert message>`
- `WWAN_ALERT=1`
- `WWAN_ALERT_TYPE`, `WWAN_ALERT_SEVERITY`, `WWAN_ALERT_INTERFACE`
- `WWAN_ALERT_SEQUENCE`, `WWAN_ALERT_TIMESTAMP`, `WWAN_ALERT_SOURCE`, `WWAN_ALERT_FSM_STATE`
- `SYSLOG_IDENTIFIER=igos-wwan-alertbus-json` (parallel JSON line)
- `MESSAGE=<compact JSON alert envelope>`
- `WWAN_ALERT_JSON=1`

This allows native `service event-handler` rules to trigger scripts from WWAN
alerts without replacing the structured D-Bus AlertBus API.

#### Event-handler + HTTPS webhook note

The IGOS `service event-handler` passes only the journal `MESSAGE` text into the
script environment variable `message`. If your script needs structured JSON for
an HTTPS POST body, use `syslog-identifier igos-wwan-alertbus-json` and parse
`$message` as JSON.

---

## Implementation Files

| File | Purpose |
|---|---|
| `op-mode-definitions/show-interfaces-wwan.xml.in` | XML: `show interfaces wwan` command tree |
| `op-mode-definitions/generate-sms.xml.in` | XML: `generate interfaces wwan ... sms` command |
| `op-mode-definitions/clear-sms.xml.in` | XML: `clear interfaces wwan … sms` commands |
| `op-mode-definitions/connect.xml.in` | XML: `connect interface` (shared with PPPoE/SSTPC) |
| `op-mode-definitions/disconnect.xml.in` | XML: `disconnect interface` (shared with PPPoE/SSTPC) |
| `src/op_mode/show_wwan.py` | Python: status, hardware, sim, signal, detail handlers |
| `src/op_mode/wwan_sms.py` | Python: send, list, read, delete SMS handlers |
| `src/op_mode/connect_disconnect.py` | Python: connect/disconnect handler (shared) |
| `python/vyos/utils/wwan/wwan_client.py` | Python: `WWANClientSync` D-Bus client library |
| `python/vyos/utils/wwan/alert_adapters.py` | Python: AlertBus subscriber adapters (REST/MQTT/SNMP skeletons) |
| `python/vyos/utils/wwan/interfaces_wwan_config.py` | Python: D-Bus service — per-interface methods |
| `python/vyos/utils/wwan/interfaces_wwan_service_manager.py` | Python: D-Bus service — control plane |

---

## Quick Reference

| Operational Command | What It Does |
|---|---|
| `show interfaces wwan` | List all WWAN interfaces (summary table) |
| `show interfaces wwan detail` | Detailed standard info for all WWAN interfaces |
| `show interfaces wwan wwan0` | Standard interface info for wwan0 |
| `show interfaces wwan wwan0 status` | Connection state, IP config, signal, SMS, data usage |
| `show interfaces wwan wwan0 hardware` | Manufacturer, model, IMEI, firmware |
| `show interfaces wwan wwan0 signal` | RSSI, RSRP, RSRQ, SNR, active bands |
| `show interfaces wwan wwan0 sim` | SIM slots, IMSI, ICCID, failover, PIN/PUK status |
| `show interfaces wwan wwan0 detail` | All of the above + data usage + failover history |
| `show interfaces wwan wwan0 wait-failover-alert` | Wait for next failover-related alert |
| `show interfaces wwan wwan0 monitor-alerts` | Collect live alerts during monitor window |
| `show interfaces wwan wwan0 sms` | List all SMS messages |
| `show interfaces wwan wwan0 sms message 3` | Read SMS message #3 |
| `show interfaces wwan wwan0 event-log` | Network event log for wwan0 |
| `show interfaces wwan wwan0 event-log link` | Link-state events only |
| `connect interface wwan0` | Bring up WWAN bearer |
| `disconnect interface wwan0` | Tear down WWAN bearer |
| `generate interfaces wwan wwan0 sms number '+15551234567' message 'hello'` | Send an SMS |
| `clear interfaces wwan wwan0 sms` | Clear all SMS messages |
| `clear interfaces wwan wwan0 sms message 3` | Clear SMS message #3 |
