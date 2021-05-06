<!-- include start from bgp/afi-maximum-paths.xml.i -->
<node name="maximum-paths">
  <properties>
    <help>Forward packets over multiple paths</help>
  </properties>
  <children>
    <leafNode name="ebgp">
      <properties>
        <help>eBGP maximum paths</help>
        <valueHelp>
          <format>u32:1-256</format>
          <description>Number of paths to consider</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-256"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="ibgp">
      <properties>
        <help>iBGP maximum paths</help>
        <valueHelp>
          <format>u32:1-256</format>
          <description>Number of paths to consider</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-256"/>
        </constraint>
      </properties>
    </leafNode>
    </children>
</node>
<!-- include end -->
