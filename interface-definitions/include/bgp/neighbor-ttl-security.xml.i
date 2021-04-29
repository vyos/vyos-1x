<!-- include start from bgp/neighbor-ttl-security.xml.i -->
<node name="ttl-security">
  <properties>
    <help>Ttl security mechanism</help>
  </properties>
  <children>
    <leafNode name="hops">
      <properties>
        <help>Number of the maximum number of hops to the BGP peer</help>
        <valueHelp>
          <format>u32:1-254</format>
          <description>Number of hops</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-254"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
