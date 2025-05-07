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
            <constraint>
              <regex>[-a-zA-Z0-9]+</regex>
            </constraint>
            <constraintErrorMessage>Host name must be alphanumeric and can contain hyphens</constraintErrorMessage>
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
