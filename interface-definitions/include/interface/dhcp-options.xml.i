<!-- include start from interface/dhcp-options.xml.i -->
<node name="dhcp-options">
  <properties>
    <help>DHCP client settings/options</help>
  </properties>
  <children>
    <leafNode name="client-id">
      <properties>
        <help>Identifier used by client to identify itself to the DHCP server</help>
      </properties>
    </leafNode>
    <leafNode name="host-name">
      <properties>
        <help>Override system host-name sent to DHCP server</help>
      </properties>
    </leafNode>
    <leafNode name="mtu">
      <properties>
        <help>Use MTU value from DHCP server - ignore interface setting</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="vendor-class-id">
      <properties>
        <help>Identify the vendor client type to the DHCP server</help>
      </properties>
    </leafNode>
    #include <include/interface/no-default-route.xml.i>
    #include <include/interface/default-route-distance.xml.i>
    <leafNode name="reject">
      <properties>
        <help>IP addresses or subnets from which to reject DHCP leases</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address to match</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 prefix to match</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
          <validator name="ipv4-prefix"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
