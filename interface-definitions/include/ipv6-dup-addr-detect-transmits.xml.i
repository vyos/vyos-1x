<!-- included start from ipv6-dup-addr-detect-transmits.xml.i -->
<leafNode name="dup-addr-detect-transmits">
  <properties>
    <help>Number of NS messages to send while performing DAD (default: 1)</help>
    <valueHelp>
      <format>1-n</format>
      <description>Number of NS messages to send while performing DAD</description>
    </valueHelp>
    <valueHelp>
      <format>0</format>
      <description>Disable Duplicate Address Dectection (DAD)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--non-negative"/>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
