<!-- include start from static/static-route-tag.xml.i -->
<leafNode name="tag">
  <properties>
    <help>Tag value for this route</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>Tag value for this route</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
