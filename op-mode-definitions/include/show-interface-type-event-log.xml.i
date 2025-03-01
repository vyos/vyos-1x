<!-- included start from show-interface-type-event-log.xml.i -->
<node name="event-log">
  <properties>
    <help>Show network interface change event log</help>
  </properties>
  <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b"</command>
  <children>
    <leafNode name="route">
      <properties>
        <help>Show log for route events</help>
      </properties>
      <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b" | grep -i "\[$6\]"</command>
    </leafNode>
    <leafNode name="link">
      <properties>
        <help>Show log for network link events</help>
      </properties>
      <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b" | grep -i "\[$6\]"</command>
    </leafNode>
    <leafNode name="addr">
      <properties>
        <help>Show log for network address events</help>
      </properties>
      <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b" | grep -i "\[$6\]"</command>
    </leafNode>
    <leafNode name="neigh">
      <properties>
        <help>Show log for neighbor table events</help>
      </properties>
      <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b" | grep -i "\[$6\]"</command>
    </leafNode>
    <leafNode name="rule">
      <properties>
        <help>Show log for PBR rule change events</help>
      </properties>
      <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service --grep "\b$4\b" | grep -i "\[$6\]"</command>
    </leafNode>
  </children>
</node>
<!-- included end -->
