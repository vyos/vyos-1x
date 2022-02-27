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
    <leafNode name="vendor-class-id">
      <properties>
        <help>Identify the vendor client type to the DHCP server</help>
      </properties>
    </leafNode>
    <leafNode name="no-default-route">
      <properties>
        <help>Do not request routers from DHCP server</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="default-route-distance">
      <properties>
        <help>Distance for the default route from DHCP server</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Distance for the default route from DHCP server</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>210</defaultValue>
    </leafNode>
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
