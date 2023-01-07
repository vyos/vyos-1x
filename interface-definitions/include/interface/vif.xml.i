<!-- include start from interface/vif.xml.i -->
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
    #include <include/interface/dhcp-options.xml.i>
    #include <include/interface/dhcpv6-options.xml.i>
    #include <include/interface/disable-link-detect.xml.i>
    #include <include/interface/disable.xml.i>
    <leafNode name="egress-qos">
      <properties>
        <help>VLAN egress QoS</help>
        <valueHelp>
          <format>txt</format>
          <description>Format for qos mapping, e.g.: '0:1 1:6 7:6'</description>
        </valueHelp>
        <constraint>
          <regex>[:0-7 ]+</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7 2:3' with numbers 0-9</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="ingress-qos">
      <properties>
        <help>VLAN ingress QoS</help>
        <valueHelp>
          <format>txt</format>
          <description>Format for qos mapping, e.g.: '0:1 1:6 7:6'</description>
        </valueHelp>
        <constraint>
          <regex>[:0-7 ]+</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7 2:3' with numbers 0-9</constraintErrorMessage>
      </properties>
    </leafNode>
    #include <include/interface/ipv4-options.xml.i>
    #include <include/interface/ipv6-options.xml.i>
    #include <include/interface/mac.xml.i>
    #include <include/interface/mirror.xml.i>
    #include <include/interface/mtu-68-16000.xml.i>
    #include <include/interface/redirect.xml.i>
    #include <include/interface/vrf.xml.i>
  </children>
</tagNode>
<!-- include end -->
