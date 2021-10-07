<!-- include start from bgp/afi-path-limit.xml.i -->
<leafNode name="path-limit">
  <properties>
    <help>AS-path hopcount limit</help>
    <valueHelp>
      <format>u32:0-255</format>
      <description>AS path hop count limit</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
