<!-- include start from vpp/nat_protocol.xml.i -->
<leafNode name="protocol">
  <properties>
    <help>Protocol</help>
    <completionHelp>
      <list>tcp udp icmp all</list>
    </completionHelp>
    <valueHelp>
      <format>all</format>
      <description>All protocols (TCP, UDP, and ICMP)</description>
    </valueHelp>
    <valueHelp>
      <format>icmp</format>
      <description>Internet Control Message Protocol (ICMP)</description>
    </valueHelp>
    <valueHelp>
      <format>tcp</format>
      <description>Transmission Control Protocol (TCP)</description>
    </valueHelp>
    <valueHelp>
      <format>udp</format>
      <description>User Datagram Protocol (UDP)</description>
    </valueHelp>
    <constraint>
      <regex>(tcp|udp|icmp|all)</regex>
    </constraint>
  </properties>
  <defaultValue>all</defaultValue>
</leafNode>
<!-- include end -->
