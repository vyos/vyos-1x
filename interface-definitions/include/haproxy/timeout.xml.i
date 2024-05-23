<!-- include start from haproxy/timeout.xml.i -->
<node name="timeout">
  <properties>
    <help>Timeout options</help>
  </properties>
  <children>
    <leafNode name="check">
      <properties>
        <help>Timeout in seconds for established connections</help>
        <valueHelp>
          <format>u32:1-3600</format>
          <description>Check timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-3600"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="connect">
      <properties>
        <help>Set the maximum time to wait for a connection attempt to a server to succeed</help>
        <valueHelp>
          <format>u32:1-3600</format>
          <description>Connect timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-3600"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="server">
      <properties>
        <help>Set the maximum inactivity time on the server side</help>
        <valueHelp>
          <format>u32:1-3600</format>
          <description>Server timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-3600"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
