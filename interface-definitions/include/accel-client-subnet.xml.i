<!-- included start from accel-client-subnet.xml.i -->
<leafNode name="subnet">
  <properties>
    <help>Client IP subnet (CIDR notation)</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 address and prefix length</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
    </constraint>
    <constraintErrorMessage>Not a valid CIDR formatted prefix</constraintErrorMessage>
    <multi />
  </properties>
</leafNode>
<!-- included end -->
