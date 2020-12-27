<!-- included start from accel-client-ipv6-pool.xml.i -->
<node name="client-ipv6-pool">
  <properties>
    <help>Pool of client IPv6 addresses</help>
  </properties>
  <children>
    <tagNode name="prefix">
      <properties>
        <help>Pool of addresses used to assign to clients</help>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
      <children>
          <leafNode name="mask">
            <properties>
              <help>Prefix length used for individual client</help>
              <valueHelp>
                <format>u32:48-128</format>
                <description>Client prefix length (default: 64)</description>
              </valueHelp>
              <constraint>
                <validator name="numeric" argument="--range 48-128"/>
              </constraint>
            </properties>
          </leafNode>
      </children>
    </tagNode>
    <tagNode name="delegate">
      <properties>
        <help>Subnet used to delegate prefix through DHCPv6-PD (RFC3633)</help>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
      <children>
          <leafNode name="delegation-prefix">
            <properties>
              <help>Prefix length delegated to client</help>
              <valueHelp>
                <format>u32:32-64</format>
                <description>Delegated prefix length</description>
              </valueHelp>
              <constraint>
                <validator name="numeric" argument="--range 32-64"/>
              </constraint>
            </properties>
          </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- included end -->
