<!-- include start from interface/default-route-distance.xml.i -->
<leafNode name="default-route-distance">
  <properties>
    <help>Distance for installed default route</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Distance for the default route from DHCP server</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
  <defaultValue>210</defaultValue>
</leafNode>
<!-- include end -->
