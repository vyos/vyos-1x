<!-- included start from static-route-next-hop-vrf.xml.i -->
<leafNode name="next-hop-vrf">
  <properties>
    <help>VRF to leak route</help>
    <valueHelp>
      <format>txt</format>
      <description>Name of VRF to leak to</description>
    </valueHelp>
    <completionHelp>
      <path>protocols vrf</path>
    </completionHelp>
    <constraint>
      <regex>^[a-zA-Z0-9\-_]{1,100}$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
