<!-- included start from accel-name-server.xml.i -->
<leafNode name="name-server">
  <properties>
    <help>Domain Name Server (DNS) propagated to client</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Domain Name Server (DNS) IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Domain Name Server (DNS) IPv6 address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- included end -->
