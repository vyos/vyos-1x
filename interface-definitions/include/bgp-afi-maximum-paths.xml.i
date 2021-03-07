<!-- included start from bgp-afi-maximum-paths.xml.i -->
<leafNode name="maximum-paths">
  <properties>
    <help>Forward packets over multiple paths (eBGP)</help>
    <valueHelp>
      <format>u32:1-256</format>
      <description>Number of paths to consider</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-256"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="maximum-paths-ibgp">
  <properties>
    <help>Forward packets over multiple paths (iBGP)</help>
    <valueHelp>
      <format>u32:1-256</format>
      <description>Number of paths to consider</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-256"/>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
