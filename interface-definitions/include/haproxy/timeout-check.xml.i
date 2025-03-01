<!-- include start from haproxy/timeout-check.xml.i -->
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
<!-- include end -->
