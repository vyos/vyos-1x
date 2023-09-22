<!-- include start from dns/dynamic-service-zone.xml.i -->
<leafNode name="zone">
  <properties>
    <help>DNS zone to be updated</help>
    <valueHelp>
      <format>txt</format>
      <description>Name of DNS zone</description>
    </valueHelp>
    <constraint>
      <validator name="fqdn"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
