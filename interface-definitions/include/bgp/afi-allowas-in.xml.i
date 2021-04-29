<!-- include start from bgp/afi-allowas-in.xml.i -->
<node name="allowas-in">
  <properties>
    <help>Accept route that contains the local-as in the as-path</help>
  </properties>
  <children>
    <leafNode name="number">
      <properties>
        <help>Number of occurrences of AS number</help>
        <valueHelp>
          <format>u32:1-10</format>
          <description>Number of times AS is allowed in path</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-10"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
