<!-- include start from firewall/packet-options.xml.i -->
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
<leafNode name="packet-type">
  <properties>
    <help>Packet type</help>
    <completionHelp>
      <list>broadcast host multicast other</list>
    </completionHelp>
    <valueHelp>
      <format>broadcast</format>
      <description>Match broadcast packet type</description>
    </valueHelp>
    <valueHelp>
      <format>host</format>
      <description>Match host packet type, addressed to local host</description>
    </valueHelp>
    <valueHelp>
      <format>multicast</format>
      <description>Match multicast packet type</description>
    </valueHelp>
    <valueHelp>
      <format>other</format>
      <description>Match packet addressed to another host</description>
    </valueHelp>
    <constraint>
      <regex>(broadcast|host|multicast|other)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
