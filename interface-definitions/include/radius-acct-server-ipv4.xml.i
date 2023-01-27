<!-- include start from radius-acct-server-ipv4.xml.i -->
<node name="radius">
  <properties>
    <help>RADIUS accounting for users OpenConnect VPN sessions OpenConnect authentication mode radius</help>
  </properties>
  <children>
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
        #include <include/radius-server-acct-port.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
