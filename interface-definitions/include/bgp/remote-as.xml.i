<!-- include start from bgp/remote-as.xml.i -->
<leafNode name="remote-as">
  <properties>
    <help>Neighbor BGP AS number</help>
    <completionHelp>
      <list>external internal</list>
    </completionHelp>
    <valueHelp>
      <format>u32:1-4294967294</format>
      <description>Neighbor AS number</description>
    </valueHelp>
    <valueHelp>
      <format>external</format>
      <description>Any AS different from the local AS</description>
    </valueHelp>
    <valueHelp>
      <format>internal</format>
      <description>Neighbor AS number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967294"/>
      <regex>(external|internal)</regex>
    </constraint>
    <constraintErrorMessage>Invalid AS number</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
