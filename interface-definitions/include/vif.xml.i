<!-- included start from vif.xml.i -->
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
    #include <include/address-ipv4-ipv6-dhcp.xml.i>
    #include <include/interface-description.xml.i>
    #include <include/dhcp-options.xml.i>
    #include <include/dhcpv6-options.xml.i>
    #include <include/interface-disable-link-detect.xml.i>
    #include <include/interface-disable.xml.i>
    #include <include/interface-vrf.xml.i>
    <leafNode name="egress-qos">
      <properties>
        <help>VLAN egress QoS</help>
        <completionHelp>
          <script>echo Format for qos mapping, e.g.: '0:1 1:6 7:6'</script>
        </completionHelp>
        <constraint>
          <regex>[:0-7 ]+$</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7 2:3' with numbers 0-9</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="ingress-qos">
      <properties>
        <help>VLAN ingress QoS</help>
        <completionHelp>
          <script>echo Format for qos mapping '0:1 1:6 7:6'</script>
        </completionHelp>
        <constraint>
          <regex>[:0-7 ]+$</regex>
        </constraint>
        <constraintErrorMessage>QoS mapping should be in the format of '0:7 2:3' with numbers 0-9</constraintErrorMessage>
      </properties>
    </leafNode>
    <node name="ip">
      <children>
        #include <include/interface-arp-cache-timeout.xml.i>
        #include <include/interface-disable-arp-filter.xml.i>
        #include <include/interface-disable-forwarding.xml.i>
        #include <include/interface-enable-arp-accept.xml.i>
        #include <include/interface-enable-arp-announce.xml.i>
        #include <include/interface-enable-arp-ignore.xml.i>
        #include <include/interface-enable-proxy-arp.xml.i>
        #include <include/interface-proxy-arp-pvlan.xml.i>
      </children>
    </node>
    <node name="ipv6">
      <children>
        #include <include/ipv6-address.xml.i>
        #include <include/ipv6-disable-forwarding.xml.i>
        #include <include/ipv6-dup-addr-detect-transmits.xml.i>
      </children>
    </node>
    #include <include/interface-mac.xml.i>
    #include <include/interface-mtu-68-9000.xml.i>
  </children>
</tagNode>
<!-- included end -->
