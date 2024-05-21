<!-- include start from qos/class-match-vif.xml.i -->
<leafNode name="vif">
  <properties>
    <help>Virtual Local Area Network (VLAN) ID for this match</help>
    <valueHelp>
      <format>u32:0-4095</format>
      <description>Virtual Local Area Network (VLAN) tag </description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4095"/>
    </constraint>
    <constraintErrorMessage>VLAN ID must be between 0 and 4095</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
