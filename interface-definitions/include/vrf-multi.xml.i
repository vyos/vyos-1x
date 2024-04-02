<!-- include start from interface/vrf.xml.i -->
<leafNode name="vrf">
  <properties>
    <help>VRF instance name</help>
    <completionHelp>
      <path>vrf name</path>
      <list>default</list>
    </completionHelp>
    <valueHelp>
      <format>default</format>
      <description>Explicitly start in default VRF</description>
    </valueHelp>
    <valueHelp>
      <format>txt</format>
      <description>VRF instance name</description>
    </valueHelp>
    #include <include/constraint/vrf.xml.i>
    <multi/>
  </properties>
  <defaultValue>default</defaultValue>
</leafNode>
<!-- include end -->
