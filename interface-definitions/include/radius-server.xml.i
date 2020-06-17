<node name="radius">
  <properties>
    <help>RADIUS based user authentication</help>
  </properties>
  <children>
    <leafNode name="source-address">
      <properties>
        <help>RADIUS client source address</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 source-address of RADIUS queries</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
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
              <format>1-65535</format>
              <description>Numeric IP port (default: 1812)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
