<!-- include start from firewall/packet-length.xml.i -->
<leafNode name="packet-length">
  <properties>
    <help>Payload size in bytes, including header and data</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Packet length value. Multiple values can be specified as a comma-separated list. Inverted match is also supported</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Packet length range. Inverted match is also supported (e.g. 1001-1005 or !1001-1005)</description>
    </valueHelp>
    <constraint>
      <validator name="packet-length"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
