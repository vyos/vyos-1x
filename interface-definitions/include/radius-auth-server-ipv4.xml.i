<!-- include start from radius-auth-server-ipv4.xml.i -->
<node name="radius">
  <properties>
    <help>RADIUS based user authentication</help>
  </properties>
  <children>
    #include <include/source-address-ipv4.xml.i>
    <tagNode name="server">
      <properties>
        <help>RADIUS server configuration</help>
        <valueHelp>
          <format>ipv4</format>
          <description>RADIUS server IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/radius-server-key.xml.i>
        #include <include/radius-server-auth-port.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
