<!-- include start from vpp/vif.xml.i -->
<tagNode name="vif">
  <properties>
    <help>Virtual Local Area Network (VLAN) ID</help>
    <valueHelp>
      <format>u32:0-4094</format>
      <description>Virtual Local Area Network (VLAN) ID</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4094"/>
    </constraint>
    <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
  </properties>
  <children>
    #include <include/generic-description.xml.i>
    #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface/disable.xml.i>
    #include <include/interface/mtu-68-16000.xml.i>
  </children>
</tagNode>
<!-- include end -->
