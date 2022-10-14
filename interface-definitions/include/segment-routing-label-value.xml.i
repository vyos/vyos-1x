<!-- include start from segment-routing-label-value.xml.i -->
<leafNode name="low-label-value">
  <properties>
    <help>MPLS label lower bound</help>
    <valueHelp>
      <format>u32:16-1048575</format>
      <description>Label value (recommended minimum value: 300)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 16-1048575"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="high-label-value">
  <properties>
    <help>MPLS label upper bound</help>
    <valueHelp>
      <format>u32:16-1048575</format>
      <description>Label value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 16-1048575"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
