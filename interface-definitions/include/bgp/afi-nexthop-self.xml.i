<!-- include start from bgp/afi-nexthop-self.xml.i -->
<node name="nexthop-self">
  <properties>
    <help>Disable the next hop calculation for this peer</help>
  </properties>
  <children>
    <leafNode name="force">
      <properties>
        <help>Set the next hop to self for reflected routes</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
