<!-- include start from radius-nas-ip-address.xml.i -->
<leafNode name="nas-ip-address">
  <properties>
    <help>NAS-IP-Address attribute sent to RADIUS</help>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
    <valueHelp>
      <format>ipv4</format>
      <description>NAS-IP-Address attribute</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->
