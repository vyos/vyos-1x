<!-- include start from accel-ppp/client-ipv6-pool.xml.i -->
<tagNode name="client-ipv6-pool">
  <properties>
    <help>Pool of client IPv6 addresses</help>
    <valueHelp>
      <format>txt</format>
      <description>Name of IPv6 pool</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
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
              <description>Client prefix length</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 48-128"/>
            </constraint>
          </properties>
          <defaultValue>64</defaultValue>
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
</tagNode>
<!-- include end -->
