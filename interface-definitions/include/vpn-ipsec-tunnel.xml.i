<!-- include start from vpn-ipsec-tunnel.xml.i -->
<tagNode name="tunnel">
  <properties>
    <help>Peer tunnel [REQUIRED]</help>
    <valueHelp>
      <format>u32</format>
      <description>Peer tunnel [REQUIRED]</description>
    </valueHelp>
  </properties>
  <children>
    #include <include/generic-disable-node.xml.i>
    <leafNode name="esp-group">
      <properties>
        <help>ESP group name</help>
        <completionHelp>
          <path>vpn ipsec esp-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <node name="local">
      <properties>
        <help>Local parameters for interesting traffic</help>
      </properties>
      <children>
        <leafNode name="port">
          <properties>
            <help>Any TCP or UDP port</help>
            <valueHelp>
              <format>port name</format>
              <description>Named port (any name in /etc/services, e.g., http)</description>
            </valueHelp>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numbered port</description>
            </valueHelp>
          </properties>
        </leafNode>
        <leafNode name="prefix">
          <properties>
            <help>Local IPv4 or IPv6 prefix</help>
            <valueHelp>
              <format>ipv4</format>
              <description>Local IPv4 prefix</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>Local IPv6 prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
              <validator name="ipv6-prefix"/>
            </constraint>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
    #include <include/ip-protocol.xml.i>
    <node name="remote">
      <properties>
        <help>Remote parameters for interesting traffic</help>
      </properties>
      <children>
        <leafNode name="port">
          <properties>
            <help>Any TCP or UDP port</help>
            <valueHelp>
              <format>port name</format>
              <description>Named port (any name in /etc/services, e.g., http)</description>
            </valueHelp>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numbered port</description>
            </valueHelp>
          </properties>
        </leafNode>
        <leafNode name="prefix">
          <properties>
            <help>Remote IPv4 or IPv6 prefix</help>
            <valueHelp>
              <format>ipv4</format>
              <description>Remote IPv4 prefix</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>Remote IPv6 prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
              <validator name="ipv6-prefix"/>
            </constraint>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</tagNode>
<!-- include end from vpn-ipsec-tunnel.xml.i -->