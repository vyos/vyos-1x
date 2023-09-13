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
          <validator name="ip-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/radius-server-key.xml.i>
        #include <include/radius-server-auth-port.xml.i>
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
    <leafNode name="security-mode">
      <properties>
        <help>Security mode for RADIUS authentication</help>
        <completionHelp>
          <list>mandatory optional</list>
        </completionHelp>
        <valueHelp>
          <format>mandatory</format>
          <description>Deny access immediately if RADIUS answers with Access-Reject</description>
        </valueHelp>
        <valueHelp>
          <format>optional</format>
          <description>Pass to the next authentication method if RADIUS answers with Access-Reject</description>
        </valueHelp>
        <constraint>
          <regex>(mandatory|optional)</regex>
        </constraint>
      </properties>
      <defaultValue>optional</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
