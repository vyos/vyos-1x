<!-- include start from serial/service/utils/host-list.xml.i -->
<node name="multihost-list">
  <properties>
    <help>Connect to all configured hosts</help>
  </properties>
  <children>
    <tagNode name="host">
      <properties>
        <help>Trueport server-initiated host config</help>
        <valueHelp>
          <!-- table main with prio 32766 -->
          <format>u32:1-50</format>
          <description>Host ID (1-50)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-50"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="name">
          <properties>
            <help>Multihost host name</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>hostname</format>
              <description>Fully qualified host name of current host</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
              <validator name="fqdn"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="port">
          <properties>
            <help>Multihost host tcp port</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Port number</description>
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
<!-- include end -->
