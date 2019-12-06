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
    #include <include/dhcp-dhcpv6-options.xml.i>
    <leafNode name="disable-link-detect">
      <properties>
        <help>Ignore link state changes</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/interface-disable.xml.i>
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
        <leafNode name="arp-cache-timeout">
          <properties>
            <help>ARP cache entry timeout in seconds</help>
            <valueHelp>
              <format>1-86400</format>
              <description>ARP cache entry timout in seconds (default 30)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-86400"/>
            </constraint>
            <constraintErrorMessage>ARP cache entry timeout must be between 1 and 86400 seconds</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="enable-proxy-arp">
          <properties>
            <help>Enable proxy-arp on this interface</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="proxy-arp-pvlan">
          <properties>
            <help>Enable private VLAN proxy ARP on this interface</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    #include <include/interface-mac.xml.i>
    #include <include/interface-mtu-68-9000.xml.i>
  </children>
</tagNode>
