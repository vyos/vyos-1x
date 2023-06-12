<!-- include start from accel-ppp/client-ip-pool-subnet-single.xml.i -->
<leafNode name="subnet">
  <properties>
    <help>Client IP subnet (CIDR notation)</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 address and prefix length</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
      <validator name="ipv4-host"/>
    </constraint>
    <constraintErrorMessage>Not a valid IP address or prefix</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
