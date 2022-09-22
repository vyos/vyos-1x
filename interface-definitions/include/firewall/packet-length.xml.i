<!-- include start from firewall/packet-length.xml.i -->
<leafNode name="packet-length">
  <properties>
    <help>Payload size in bytes, including header and data to match</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Packet length to match</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Packet length range to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 1-65535"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<leafNode name="packet-length-exclude">
  <properties>
    <help>Payload size in bytes, including header and data not to match</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Packet length not to match</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Packet length range not to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 1-65535"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
