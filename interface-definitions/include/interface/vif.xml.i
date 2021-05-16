<!-- include start from interface/vif.xml.i -->
<tagNode name="vif">
  <properties>
    <help>Virtual Local Area Network (VLAN) ID</help>
    <valueHelp>
      <format>0-4094</format>
      <description>Virtual Local Area Network (VLAN) ID</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4094"/>
    </constraint>
    <constraintErrorMessage>VLAN ID must be between 0 and 4094</constraintErrorMessage>
  </properties>
  <children>
    #include <include/interface/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface/interface-description.xml.i>
    #include <include/interface/dhcp-options.xml.i>
    #include <include/interface/dhcpv6-options.xml.i>
    #include <include/interface/interface-disable-link-detect.xml.i>
    #include <include/interface/interface-disable.xml.i>
    #include <include/interface/interface-vrf.xml.i>
    <leafNode name="egress-qos">
      <properties>
        <help>VLAN egress QoS</help>
        <valueHelp>
          <format>from:to</format>
          <description>The format is FROM:TO with multiple mappings separated by spaces.</description>
        </valueHelp>
        <constraint>
          <regex>[:0-7]+$</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7' with numbers 0-9</constraintErrorMessage>
        <multi />
      </properties>
    </leafNode>
    <leafNode name="ingress-qos">
      <properties>
        <help>VLAN ingress QoS</help>
        <valueHelp>
          <format>from:to</format>
          <description>The format is FROM:TO with multiple mappings separated by spaces.</description>
        </valueHelp>
        <constraint>
          <regex>[:0-7]+$</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7' with numbers 0-9</constraintErrorMessage>
        <multi />
      </properties>
    </leafNode>
    #include <include/interface/interface-ipv4-options.xml.i>
    #include <include/interface/interface-ipv6-options.xml.i>
    #include <include/interface/interface-mac.xml.i>
    #include <include/interface/interface-mtu-68-16000.xml.i>
  </children>
</tagNode>
<!-- include end -->
