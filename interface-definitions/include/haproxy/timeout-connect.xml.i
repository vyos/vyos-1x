<!-- include start from haproxy/timeout-connect.xml.i -->
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
<!-- include end -->
