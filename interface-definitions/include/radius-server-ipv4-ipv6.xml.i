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
  </children>
</node>
<!-- include end -->
