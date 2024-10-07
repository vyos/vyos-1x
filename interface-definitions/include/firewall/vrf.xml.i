<!-- include start from firewall/vrf.xml.i -->
<leafNode name="vrf">
  <properties>
    <help>VRF to forward packet with</help>
    <valueHelp>
      <format>txt</format>
      <description>VRF instance name</description>
    </valueHelp>
    <valueHelp>
      <format>default</format>
      <description>Forward into default global VRF</description>
    </valueHelp>
    <completionHelp>
      <list>default</list>
      <path>vrf name</path>
    </completionHelp>
    #include <include/constraint/vrf.xml.i>
  </properties>
</leafNode>
<!-- include end -->
