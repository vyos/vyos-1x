<!-- include start from static/static-route-distance.xml.i -->
<leafNode name="distance">
  <properties>
    <help>Distance for this route</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Distance for this route</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
