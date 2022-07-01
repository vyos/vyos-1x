<!-- include start from interface/address-ipv4-ipv6-dhcp.xml.i -->
<leafNode name="address">
  <properties>
    <help>IP address</help>
    <completionHelp>
      <list>dhcp dhcpv6</list>
    </completionHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 address and prefix length</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 address and prefix length</description>
    </valueHelp>
    <valueHelp>
      <format>dhcp</format>
      <description>Dynamic Host Configuration Protocol</description>
    </valueHelp>
    <valueHelp>
      <format>dhcpv6</format>
      <description>Dynamic Host Configuration Protocol for IPv6</description>
    </valueHelp>
    <constraint>
      <validator name="ip-host"/>
      <regex>(dhcp|dhcpv6)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
