<!-- include start from vni.xml.i -->
<leafNode name="vni">
  <properties>
    <help>Virtual Network Identifier</help>
    <valueHelp>
      <format>u32:0-16777214</format>
      <description>VXLAN virtual network identifier</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-16777214"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
