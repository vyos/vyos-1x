<!-- include start from snmp/protocol.xml.i -->
<leafNode name="protocol">
  <properties>
    <help>Protocol to be used (TCP/UDP)</help>
    <completionHelp>
      <list>udp tcp</list>
    </completionHelp>
    <valueHelp>
      <format>udp</format>
      <description>Listen protocol UDP (default)</description>
    </valueHelp>
    <valueHelp>
      <format>tcp</format>
      <description>Listen protocol TCP</description>
    </valueHelp>
    <constraint>
      <regex>^(udp|tcp)$</regex>
    </constraint>
  </properties>
  <defaultValue>udp</defaultValue>
</leafNode>
<!-- include end -->
