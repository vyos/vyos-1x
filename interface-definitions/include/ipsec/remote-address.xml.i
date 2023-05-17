<!-- include start from ipsec/remote-address.xml.i -->
<leafNode name="remote-address">
  <properties>
    <help>IPv4 or IPv6 address of the remote peer</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address of the remote peer</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address of the remote peer</description>
    </valueHelp>
    <valueHelp>
      <format>hostname</format>
      <description>Fully qualified domain name of the remote peer</description>
    </valueHelp>
    <valueHelp>
      <format>any</format>
      <description>Allow any IP address of the remote peer</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
      <validator name="fqdn"/>
      <regex>(any)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
