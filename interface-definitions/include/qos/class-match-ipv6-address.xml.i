<!-- include start from qos/class-match-ipv6-address.xml.i -->
<leafNode name="address">
  <properties>
    <help>IPv6 destination address for this match</help>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 address and prefix length</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
