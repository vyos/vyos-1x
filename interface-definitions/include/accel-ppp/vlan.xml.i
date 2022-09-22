<!-- include start from accel-ppp/vlan.xml.i -->
<leafNode name="vlan">
  <properties>
    <help>VLAN monitor for automatic creation of VLAN interfaces</help>
    <valueHelp>
      <format>u32:1-4094</format>
      <description>VLAN for automatic creation</description>
    </valueHelp>
    <valueHelp>
      <format>start-end</format>
      <description>VLAN range for automatic creation (e.g. 1-4094)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 1-4094"/>
    </constraint>
    <constraintErrorMessage>VLAN IDs need to be in range 1-4094</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
