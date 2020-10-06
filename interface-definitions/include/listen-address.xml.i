<!-- included start from listen-address.xml.i -->
<leafNode name="listen-address">
  <properties>
    <help>Local IP addresses for service to listen on</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IP address to listen for incoming connections</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address to listen for incoming connections</description>
    </valueHelp>
    <multi/>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
