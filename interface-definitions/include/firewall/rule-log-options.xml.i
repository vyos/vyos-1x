<!-- include start from firewall/rule-log-options.xml.i -->
<node name="log-options">
   <properties>
    <help>Log options</help>
  </properties>
  <children>
    <leafNode name="group">
      <properties>
        <help>Set log group</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Log group to send messages to</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="snapshot-length">
      <properties>
        <help>Length of packet payload to include in netlink message</help>
        <valueHelp>
          <format>u32:0-9000</format>
          <description>Length of packet payload to include in netlink message</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-9000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="queue-threshold">
      <properties>
        <help>Number of packets to queue inside the kernel before sending them to userspace</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Number of packets to queue inside the kernel before sending them to userspace</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="level">
      <properties>
        <help>Set log-level</help>
        <completionHelp>
          <list>emerg alert crit err warn notice info debug</list>
        </completionHelp>
        <valueHelp>
          <format>emerg</format>
          <description>Emerg log level</description>
        </valueHelp>
        <valueHelp>
          <format>alert</format>
          <description>Alert log level</description>
        </valueHelp>
        <valueHelp>
          <format>crit</format>
          <description>Critical log level</description>
        </valueHelp>
        <valueHelp>
          <format>err</format>
          <description>Error log level</description>
        </valueHelp>
        <valueHelp>
          <format>warn</format>
          <description>Warning log level</description>
        </valueHelp>
        <valueHelp>
          <format>notice</format>
          <description>Notice log level</description>
        </valueHelp>
        <valueHelp>
          <format>info</format>
          <description>Info log level</description>
        </valueHelp>
        <valueHelp>
          <format>debug</format>
          <description>Debug log level</description>
        </valueHelp>
        <constraint>
          <regex>(emerg|alert|crit|err|warn|notice|info|debug)</regex>
        </constraint>
        <constraintErrorMessage>level must be alert, crit, debug, emerg, err, info, notice or warn</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->