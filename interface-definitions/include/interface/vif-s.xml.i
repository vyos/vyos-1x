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
    #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface/description.xml.i>
    #include <include/interface/dhcp-options.xml.i>
    #include <include/interface/dhcpv6-options.xml.i>
    #include <include/interface/disable-link-detect.xml.i>
    #include <include/interface/disable.xml.i>
    #include <include/interface/interface-policy-vif.xml.i>
    <leafNode name="protocol">
      <properties>
        <help>Protocol used for service VLAN (default: 802.1ad)</help>
        <completionHelp>
          <list>802.1ad 802.1q</list>
        </completionHelp>
        <valueHelp>
          <format>802.1ad</format>
          <description>Provider Bridging (IEEE 802.1ad, Q-inQ), ethertype 0x88a8</description>
        </valueHelp>
        <valueHelp>
          <format>802.1q</format>
          <description>VLAN-tagged frame (IEEE 802.1q), ethertype 0x8100</description>
        </valueHelp>
        <constraint>
          <regex>(802.1q|802.1ad)</regex>
        </constraint>
        <constraintErrorMessage>Ethertype must be 802.1ad or 802.1q</constraintErrorMessage>
      </properties>
      <defaultValue>802.1ad</defaultValue>
    </leafNode>
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
        #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
        #include <include/interface/description.xml.i>
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
        #include <include/interface/interface-policy-vif-c.xml.i>
      </children>
    </tagNode>
    #include <include/interface/redirect.xml.i>
    #include <include/interface/vrf.xml.i>
  </children>
</tagNode>
<!-- include end -->
