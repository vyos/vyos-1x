<!-- include start from radius-server-ipv4-ipv6.xml.i -->
<node name="radius">
  <properties>
    <help>RADIUS based user authentication</help>
  </properties>
  <children>
    <tagNode name="server">
      <properties>
        <help>RADIUS server configuration</help>
        <valueHelp>
          <format>ipv4</format>
          <description>RADIUS server IPv4 address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>RADIUS server IPv6 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
          <validator name="ipv6-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/radius-server-key.xml.i>
        #include <include/radius-server-port.xml.i>
      </children>
    </tagNode>
    <leafNode name="source-address">
      <properties>
        <help>Source IP address used to initiate connection</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_local_ips.sh --both</script>
        </completionHelp>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 source address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 source address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
          <validator name="ipv6-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
