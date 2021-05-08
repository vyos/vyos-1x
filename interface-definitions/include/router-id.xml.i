<!-- include start from router-id.xml.i -->
<leafNode name="router-id">
  <properties>
    <help>Override default router identifier</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Router-ID in IP address format</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
