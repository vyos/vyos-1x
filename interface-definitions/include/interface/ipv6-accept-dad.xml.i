<!-- include start from interface/ipv6-accept-dad.xml.i -->
<leafNode name="accept-dad">
  <properties>
    <help>Accept Duplicate Address Detection</help>
    <valueHelp>
      <format>0</format>
      <description>Disable DAD</description>
    </valueHelp>
    <valueHelp>
      <format>1</format>
      <description>Enable DAD</description>
    </valueHelp>
    <valueHelp>
      <format>2</format>
      <description>Enable DAD - disable IPv6 if MAC-based duplicate link-local address found</description>
    </valueHelp>
  </properties>
  <defaultValue>1</defaultValue>
</leafNode>
<!-- include end -->
