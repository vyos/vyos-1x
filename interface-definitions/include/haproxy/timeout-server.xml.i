<!-- include start from haproxy/timeout-server.xml.i -->
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
<!-- include end -->
