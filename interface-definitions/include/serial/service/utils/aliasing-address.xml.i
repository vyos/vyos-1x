<!-- include start from serial/service/utils/aliasing-address.xml.i -->
<leafNode name="inet">
  <properties>
    <help>Alias IP Address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
