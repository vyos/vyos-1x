<!-- include start from interface/tunnel-remote-multi.xml.i -->
<leafNode name="remote">
  <properties>
    <help>Tunnel remote address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Tunnel remote IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Tunnel remote IPv6 address</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
