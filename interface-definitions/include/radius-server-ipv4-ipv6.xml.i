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
    #include <include/source-address-ipv4-ipv6-multi.xml.i>
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
