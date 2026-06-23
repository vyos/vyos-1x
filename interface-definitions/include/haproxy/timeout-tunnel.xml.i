<!-- include start from haproxy/timeout-tunnel.xml.i -->
<leafNode name="tunnel">
  <properties>
    <help>Set the maximum inactivity time on the client and server side for tunnels</help>
    <valueHelp>
      <format>u32:1-86400</format>
      <description>Tunnel timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-86400"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
