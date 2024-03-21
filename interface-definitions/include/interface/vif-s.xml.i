<!-- include start from interface/vif-s.xml.i -->
<tagNode name="vif-s">
  <properties>
    <help>QinQ TAG-S Virtual Local Area Network (VLAN) ID</help>
    <valueHelp>
      <format>u32:0-4094</format>
      <description>QinQ Virtual Local Area Network (VLAN) ID</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4094"/>
    </constraint>
    <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
  </properties>
  <children>
    #include <include/generic-description.xml.i>
    #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface/dhcp-options.xml.i>
    #include <include/interface/dhcpv6-options.xml.i>
    #include <include/interface/disable-link-detect.xml.i>
    #include <include/interface/disable.xml.i>
    #include <include/interface/vlan-protocol.xml.i>
    #include <include/interface/ipv4-options.xml.i>
    #include <include/interface/ipv6-options.xml.i>
    #include <include/interface/mac.xml.i>
    #include <include/interface/mirror.xml.i>
    #include <include/interface/mtu-68-16000.xml.i>
    <tagNode name="vif-c">
      <properties>
        <help>QinQ TAG-C Virtual Local Area Network (VLAN) ID</help>
        <constraint>
          <validator name="numeric" argument="--range 0-4094"/>
        </constraint>
        <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
      </properties>
      <children>
        #include <include/generic-description.xml.i>
        #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
        #include <include/interface/dhcp-options.xml.i>
        #include <include/interface/dhcpv6-options.xml.i>
        #include <include/interface/disable-link-detect.xml.i>
        #include <include/interface/disable.xml.i>
        #include <include/interface/ipv4-options.xml.i>
        #include <include/interface/ipv6-options.xml.i>
        #include <include/interface/mac.xml.i>
        #include <include/interface/mirror.xml.i>
        #include <include/interface/mtu-68-16000.xml.i>
        #include <include/interface/redirect.xml.i>
        #include <include/interface/vrf.xml.i>
      </children>
    </tagNode>
    #include <include/interface/redirect.xml.i>
    #include <include/interface/vrf.xml.i>
  </children>
</tagNode>
<!-- include end -->
