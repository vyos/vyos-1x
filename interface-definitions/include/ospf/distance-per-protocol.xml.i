<!-- include start from ospf/distance-per-protocol.xml.i -->
<leafNode name="external">
  <properties>
    <help>Distance for external routes</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Distance for external routes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="inter-area">
  <properties>
    <help>Distance for inter-area routes</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Distance for inter-area routes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="intra-area">
  <properties>
    <help>Distance for intra-area routes</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Distance for intra-area routes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
