<!-- include start from dhcp/ntp-server.xml.i -->
<leafNode name="ntp-server">
  <properties>
    <help>IP address of NTP server</help>
    <valueHelp>
      <format>ipv4</format>
      <description>NTP server IPv4 address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
