# VyOS Alerting Subsystem — Work List / Roadmap

Stand-alone roadmap to evolve from the current WWAN-only AlertBus into a
box-wide, vendor-grade alerting subsystem (Cisco EEM / Junos event-policy
shaped).  Each stage is independently shippable.

---

## Stage 0 — Baseline (already in tree)

- [x] Stable alert envelope: `id, code, severity, category, source, state,
      timestamp, interface_number, message, extra`.
- [x] WWAN FSM emits structured alerts via `_emit_alert` /
      `_emit_failover_event` (see `python/vyos/utils/wwan/interfaces_wwan_state_machine.py`).
- [x] AlertBus + `AlertSubscriptionRunner` in
      `python/vyos/utils/wwan/alert_adapters.py`.
- [x] D-Bus `AlertBusInterface` exported by WWAN service manager
      (`com.igos.IgosModemManager.AlertBus`).
- [x] Op-mode helpers: `wait-failover-alert`, `monitor-alerts`.

**Treat the envelope as a stable API surface.  Codes are append-only.**

---

## Stage 1 — Make alerts actually leave the box

Goal: any WWAN alert reaches an HTTP API and/or SNMP trap target today.

### 1.1 `HttpAlertAdapter` (highest priority)
- [ ] POST normalized envelope as JSON.
- [ ] Auth: bearer token and/or HMAC signing (configurable).
- [ ] Async retry with exponential backoff + jitter.
- [ ] **On-disk spool** at `/var/spool/vyos-alerts/*.json` when endpoint is
      unreachable — critical for cellular/edge.
- [ ] Drain spool on reconnect, in-order, with rate cap.
- [ ] Unit tests: happy path, network failure, spool replay, malformed reply.

### 1.2 `vyos-alertd` daemon
- [ ] New systemd unit: `src/systemd/vyos-alertd.service`.
- [ ] Reads `/etc/vyos/alertd.yaml` (rendered by conf-mode).
- [ ] Connects to existing AlertBus D-Bus interface.
- [ ] Builds an `AlertSubscriptionRunner` and registers configured adapters.
- [ ] Hot-reload on SIGHUP.
- [ ] Drops privileges; runs as `vyos-alertd` user with access only to
      `/var/spool/vyos-alerts/` and `/etc/vyos/alertd.yaml`.

### 1.3 CLI front-end
- [ ] New XML: `interface-definitions/service_alert.xml.in`.
- [ ] Conf-mode: `src/conf_mode/service_alert.py` → renders `alertd.yaml`,
      reloads daemon.
- [ ] Nodes:
  ```
  set service alert endpoint http NAME url <url>
  set service alert endpoint http NAME auth bearer-token <token>
  set service alert endpoint http NAME auth hmac-secret <secret>
  set service alert endpoint http NAME spool-path <path>
  set service alert endpoint snmp NAME trap-target <ip>
  set service alert endpoint snmp NAME community <c>
  set service alert sink file path <path>
  set service alert sink script path <path>
  set service alert filter <NAME> severity <info|warning|critical>
  set service alert filter <NAME> category <…>
  ```

### 1.4 Op-mode commands
- [ ] `show service alert active` → from `RestAlertAdapter.get_active()`.
- [ ] `show service alert history [last N]` → from recent ring buffer.
- [ ] `show service alert endpoints status` → spool depth, last success.

**Exit criteria:** WWAN alerts delivered to HTTP and/or SNMP, survive reboot
of either side, single config surface.

---

## Stage 2 — Bring the rest of the box in via a journal shim

Goal: BGP/OSPF/IPsec/firewall/DHCP/kernel/link events become normalized
alerts without patching VyOS internals.

### 2.1 `JournalSource` inside `vyos-alertd`
- [ ] `journalctl --output=json --follow --merge` reader.
- [ ] Per-message classifier with compiled regex cache.
- [ ] Backpressure-safe queue between reader and AlertBus publisher.
- [ ] Restart-resilient cursor (persist last journal cursor on shutdown).

### 2.2 Rule pack
- [ ] `/usr/share/vyos-alert-rules/*.yaml` — shipped defaults.
- [ ] `/etc/vyos/alert-rules.d/*.yaml` — operator overrides.
- [ ] Rule schema:
  ```yaml
  - match: { SYSLOG_IDENTIFIER: bgpd, MESSAGE_RE: "neighbor (\\S+) Down" }
    emit:  { code: BGP_NEIGHBOR_DOWN, severity: warning, category: routing,
             source: "bgp/{group1}", state: open }
  - match: { SYSLOG_IDENTIFIER: bgpd, MESSAGE_RE: "neighbor (\\S+) Up" }
    emit:  { code: BGP_NEIGHBOR_UP, severity: info, category: routing,
             source: "bgp/{group1}", state: cleared,
             related: BGP_NEIGHBOR_DOWN }
  ```
- [ ] State engine: `state: cleared` with `related:` closes matching open
      alerts in `RestAlertAdapter.active_by_id`.

### 2.3 Starter rule coverage (~20 rules)
- [ ] FRR: BGP up/down, OSPF adjacency change, IS-IS adjacency, BFD up/down.
- [ ] strongSwan/charon: IKE_SA established/closed, CHILD_SA up/down,
      auth failure.
- [ ] Kea DHCP: pool exhaustion, lease decline, server start/stop.
- [ ] Kernel: link up/down, OOM, watchdog, thermal.
- [ ] nftables: counter threshold (via custom log targets).
- [ ] systemd: unit failed, oom-kill.

### 2.4 Tooling
- [ ] `vyos-alert-rules validate <file>` — schema + regex syntax check.
- [ ] `vyos-alert-rules test <file> --journal-cursor=<…>` — replay against
      historical journal entries.

**Exit criteria:** ~80% subsystem coverage, no patches to VyOS internals,
adding a new code is a YAML line.

---

## Stage 3 — Replace `service event-handler` cleanly

Goal: keep the user-facing CLI, retire the redundant daemon.

- [ ] Implement `ScriptAlertAdapter` in
      `python/vyos/utils/wwan/alert_adapters.py` (or move adapters into
      `python/vyos/alerts/`):
  - Runs script with env vars: `ALERT_CODE`, `ALERT_SEVERITY`,
    `ALERT_CATEGORY`, `ALERT_SOURCE`, `ALERT_MESSAGE`, `ALERT_ID`,
    `ALERT_STATE`, `ALERT_TIMESTAMP`, plus extras as `ALERT_EXTRA_*`.
  - Configurable timeout, kill on overrun.
- [ ] Rewrite `src/conf_mode/service_event-handler.py`:
  - Compile each `event-handler event NAME { filter pattern, script path }`
    into a YAML rule + `ScriptAlertAdapter` registration in `alertd.yaml`.
  - Preserve existing CLI verbatim — no customer-visible breakage.
- [ ] Remove `src/systemd/vyos-event-handler.service`.
- [ ] Migration test: existing event-handler configs continue to fire.

**Exit criteria:** one daemon (`vyos-alertd`), zero CLI regressions.

---

## Stage 4 — Native emit for high-value subsystems

Goal: state nobody can derive from a log line, structured at source.

### 4.1 Library
- [ ] `python/vyos/alerts/emit.py` providing
      `emit(code, severity, category, source, message, **extra)`.
- [ ] Thin shim that publishes to AlertBus over D-Bus (so any VyOS Python
      script can emit without owning the bus).

### 4.2 Targets (priority order)
- [ ] WAN failover decisions (already partially done — finish hooking
      reconnect/recovery codes).
- [ ] BFD session state (not in any standard MIB).
- [ ] BGP richer events (max-prefix, hold-timer expiry, NOTIFICATION
      received with subcode).
- [ ] IPsec rekey reasons / DPD timeouts.
- [ ] conntrack table threshold breach.
- [ ] Kea pool exhaustion (precise lease counts).
- [ ] PKI: certificate expiry warnings (30/14/7/1 day).
- [ ] Hardware: sensors (lm-sensors), thermal, fan, PSU.
- [ ] HA / VRRP state transitions (not always logged at usable severity).

### 4.3 Documentation discipline
- [ ] `docs/alerts/codes.md` — single source of truth:
      `code | severity | category | meaning | extra fields | first version`.
- [ ] Codes are **append-only**.  Document deprecation policy.
- [ ] Per-code OID assignment in `docs/alerts/snmp-oids.md`, only after
      the code exists.

**Exit criteria:** parity-shaped coverage with EEM/Junos event policy on
the items that matter for the product.

---

## Stage 5 — Streaming telemetry (optional)

Goal: continuous state, not just discrete alerts.

- [ ] New `MetricsBus` mirroring AlertBus pattern.
- [ ] `PrometheusExporterAdapter` — HTTP `/metrics`.
- [ ] `OtlpAdapter` — gRPC push to OpenTelemetry collector.
- [ ] Keep separate from alerts — different lifecycle, different consumers.

---

## Cross-cutting work

### Code/file moves
- [ ] Promote alert adapters out of `python/vyos/utils/wwan/` to
      `python/vyos/alerts/` once they serve more than WWAN.
- [ ] Keep WWAN-specific imports working via shim (`from
      vyos.utils.wwan.alert_adapters import *`) for one release.

### FRR AgentX (small, parallel win)
- [ ] CLI: `set service snmp frr-agentx`.
- [ ] Conf-mode renders `agentx` into each enabled FRR daemon's config.
- [ ] Conf-mode adds `master agentx` to `snmpd.conf`.
- [ ] Gives free standard BGP4-MIB / OSPF-MIB traps without writing a MIB.

### Stable-ID discipline (apply from Stage 1)
- [ ] Codes uppercase, namespaced: `WWAN_*`, `BGP_*`, `OSPF_*`, `IPSEC_*`,
      `LINK_*`, `FW_*`, `DHCP_*`, `PKI_*`, `HW_*`, `HA_*`, `SYS_*`.
- [ ] Append-only.  Renames break automation.
- [ ] CI check: `docs/alerts/codes.md` must contain every code referenced
      in source.

### Security
- [ ] HTTP endpoint TLS verification on by default.
- [ ] Spool directory mode 0700, owned by `vyos-alertd`.
- [ ] Rate-limit per-code to prevent log-flood DoS.
- [ ] Redact sensitive fields (PIN/PUK, bearer tokens) before emit.

### Testing
- [ ] Unit tests for each adapter (mock transport).
- [ ] Integration test harness: simulated journal feed → expected alert
      sequence.
- [ ] Smoke test in `smoketest/` for `service alert` config rendering.

---

## Suggested execution order (week-scale)

| # | Item | Stage | Effort | Payoff |
|---|------|-------|--------|--------|
| 1 | `HttpAlertAdapter` + spool + tests | 1 | M | XL |
| 2 | `vyos-alertd` skeleton + D-Bus subscribe | 1 | M | XL |
| 3 | `set service alert endpoint http …` CLI | 1 | M | L |
| 4 | `JournalSource` + first 5 BGP/link rules | 2 | M | XL |
| 5 | Rule schema validator + test tool | 2 | S | M |
| 6 | Expand rules to 20 starter coverage | 2 | M | XL |
| 7 | `ScriptAlertAdapter` + event-handler rewrite | 3 | M | M |
| 8 | `python/vyos/alerts/emit.py` shim | 4 | S | M |
| 9 | Native emit: BFD, BGP-extra, IPsec, PKI expiry | 4 | L | L |
| 10 | FRR AgentX CLI knob | parallel | S | M |
| 11 | `docs/alerts/codes.md` + CI gate | parallel | S | L |
| 12 | Prometheus/OTLP metrics | 5 | L | (later) |

S = small, M = medium, L = large; payoff S < M < L < XL.

---

## Open questions to resolve before Stage 1

- [ ] Endpoint identity model — one HTTP endpoint or N named endpoints?
- [ ] Alert envelope schema versioning: `schema: 1`, deprecation policy.
- [ ] How to handle clock skew between box and collector (timestamps).
- [ ] Backpressure policy: drop oldest / drop newest / block when spool
      hits cap.
- [ ] Multi-tenancy: do customers run multiple AlertBus consumers?
      (today: yes — op-mode + alertd).

---

## References (in-tree)

- `python/vyos/utils/wwan/alert_adapters.py` — adapter skeletons.
- `python/vyos/utils/wwan/interfaces_wwan_state_machine.py` —
  `_emit_alert`, `_emit_failover_event` callsites.
- `python/vyos/utils/wwan/interfaces_wwan_service_manager.py` —
  `AlertBusInterface` D-Bus export.
- `python/vyos/utils/wwan/wwan_client.py` — AlertBus subscriber API.
- `docs/vyos-wwan-operational-commands.md` —
  existing alert-related op-mode commands.
- `src/conf_mode/service_event-handler.py` — to be replaced in Stage 3.
- `interface-definitions/service_event-handler.xml.in` — CLI to preserve.
