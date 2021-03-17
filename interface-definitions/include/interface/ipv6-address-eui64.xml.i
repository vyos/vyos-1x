<!-- include start from interface/ipv6-address-eui64.xml.i -->
<leafNode name="eui64">
  <properties>
    <help>Prefix for IPv6 address with MAC-based EUI-64</help>
    <valueHelp>
      <format>&lt;h:h:h:h:h:h:h:h/64&gt;</format>
      <description>IPv6 /64 network</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-eui64-prefix"/>
    </constraint>
    <constraintErrorMessage>EUI64 prefix length must be 64</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
