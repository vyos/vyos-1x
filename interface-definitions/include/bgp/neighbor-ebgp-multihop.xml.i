<!-- include start from bgp/neighbor-ebgp-multihop.xml.i -->
<leafNode name="ebgp-multihop">
  <properties>
    <help>Allow this EBGP neighbor to not be on a directly connected network</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Number of hops</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
