<!-- include start from accel-ppp/gateway-address.xml.i -->
<leafNode name="gateway-address">
  <properties>
    <help>Gateway IP address</help>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
    <constraintErrorMessage>invalid IPv4 address</constraintErrorMessage>
    <valueHelp>
      <format>ipv4</format>
      <description>Default Gateway send to the client</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->
