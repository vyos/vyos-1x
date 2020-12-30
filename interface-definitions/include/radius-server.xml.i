<!-- included start from radius-server.xml.i -->
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
        <leafNode name="disable">
          <properties>
            <help>Temporary disable this server</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="key">
          <properties>
            <help>Shared secret key</help>
          </properties>
        </leafNode>
        <leafNode name="port">
          <properties>
            <help>Authentication port</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numeric IP port (default: 1812)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
          <defaultValue>1812</defaultValue>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- included end -->
