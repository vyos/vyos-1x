<!-- include start from haproxy/timeout-client.xml.i -->
<leafNode name="client">
  <properties>
    <help>Maximum inactivity time on the client side</help>
    <valueHelp>
      <format>u32:1-3600</format>
      <description>Timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-3600"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
