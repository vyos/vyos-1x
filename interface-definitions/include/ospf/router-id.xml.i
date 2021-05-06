<!-- include start from ospf/router-id.xml.i -->
<leafNode name="router-id">
  <properties>
    <help>Override the default router identifier</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Override the default router identifier</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
