<!-- include start from bgp/afi-attribute-unchanged.xml.i -->
<node name="attribute-unchanged">
  <properties>
    <help>BGP attributes are sent unchanged</help>
  </properties>
  <children>
    <leafNode name="as-path">
      <properties>
        <help>Send AS path unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="med">
      <properties>
        <help>Send multi-exit discriminator unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="next-hop">
      <properties>
        <help>Send nexthop unchanged</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
