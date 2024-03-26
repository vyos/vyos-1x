<!-- include start from accel-ppp/gateway-address-multi.xml.i -->
<leafNode name="gateway-address">
  <properties>
    <help>Gateway IP address</help>
    <constraintErrorMessage>invalid IPv4 address</constraintErrorMessage>
    <valueHelp>
      <format>ipv4net</format>
      <description>Default Gateway, mask send to the client</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
      <validator name="ipv4-host"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
