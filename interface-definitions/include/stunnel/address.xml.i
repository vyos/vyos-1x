<!-- include start from stunnel/address.xml.i -->
<leafNode name="address">
  <properties>
    <help>Hostname or IP address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>hostname</format>
      <description>hostname</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid FQDN or IP address</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
