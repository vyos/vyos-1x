<!-- include start from static/static-route-vrf.xml.i -->
<leafNode name="vrf">
  <properties>
    <help>VRF to leak route</help>
    <completionHelp>
      <list>default</list>
      <path>vrf name</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Name of VRF to leak to</description>
    </valueHelp>
    <constraint>
      <regex>(default)</regex>
      <validator name="vrf-name"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
