<!-- include start from interface/adjust-mss.xml.i -->
<!-- https://datatracker.ietf.org/doc/html/rfc6691 -->
<leafNode name="adjust-mss">
  <properties>
    <help>Adjust TCP MSS value</help>
    <completionHelp>
      <list>clamp-mss-to-pmtu</list>
    </completionHelp>
    <valueHelp>
      <format>clamp-mss-to-pmtu</format>
      <description>Automatically sets the MSS to the proper value</description>
    </valueHelp>
    <valueHelp>
      <format>u32:536-65535</format>
      <description>TCP Maximum segment size in bytes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 536-65535"/>
      <regex>(clamp-mss-to-pmtu)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
