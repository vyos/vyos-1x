<tagNode name="vif-s">
  <properties>
    <help>QinQ TAG-S Virtual Local Area Network (VLAN) ID</help>
    <constraint>
      <validator name="numeric" argument="--range 0-4094"/>
    </constraint>
    <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
  </properties>
  <children>
    #include <include/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface-description.xml.i>
    #include <include/dhcp-dhcpv6-options.xml.i>
    #include <include/interface-disable-link-detect.xml.i>
    #include <include/interface-disable.xml.i>
    <leafNode name="ethertype">
      <properties>
        <help>Set Ethertype</help>
        <completionHelp>
          <list>0x88A8 0x8100</list>
        </completionHelp>
        <valueHelp>
          <format>0x88A8</format>
          <description>802.1ad</description>
        </valueHelp>
        <valueHelp>
          <format>0x8100</format>
          <description>802.1q</description>
        </valueHelp>
        <constraint>
          <regex>(0x88A8|0x8100)</regex>
        </constraint>
        <constraintErrorMessage>Ethertype must be 0x88A8 or 0x8100</constraintErrorMessage>
      </properties>
    </leafNode>
    <node name="ip">
      <children>
        #include <include/interface-disable-arp-filter.xml.i>
        #include <include/interface-enable-arp-accept.xml.i>
        #include <include/interface-enable-arp-announce.xml.i>
        #include <include/interface-enable-arp-ignore.xml.i>
      </children>
    </node>
    #include <include/interface-mac.xml.i>
    #include <include/interface-mtu-68-9000.xml.i>
    <tagNode name="vif-c">
      <properties>
        <help>QinQ TAG-C Virtual Local Area Network (VLAN) ID</help>
        <constraint>
          <validator name="numeric" argument="--range 0-4094"/>
        </constraint>
        <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
      </properties>
      <children>
        #include <include/address-ipv4-ipv6-dhcp.xml.i>
        #include <include/interface-description.xml.i>
        #include <include/dhcp-dhcpv6-options.xml.i>
        #include <include/interface-disable-link-detect.xml.i>
        #include <include/interface-disable.xml.i>
        #include <include/interface-mac.xml.i>
        #include <include/interface-mtu-68-9000.xml.i>
        #include <include/interface-vrf.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
