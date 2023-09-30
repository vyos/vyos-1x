<!-- include start from dns/time-to-live.xml.i -->
<leafNode name="ttl">
  <properties>
    <help>Time-to-live (TTL)</help>
    <valueHelp>
      <format>u32:0-2147483647</format>
      <description>TTL in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-2147483647"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
