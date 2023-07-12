<!-- include start from bgp/afi-vpn-label.xml.i -->
<leafNode name="label">
  <properties>
    <help>MPLS label value assigned to route</help>
    <valueHelp>
      <format>u32:0-1048575</format>
      <description>MPLS label value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-1048575"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
