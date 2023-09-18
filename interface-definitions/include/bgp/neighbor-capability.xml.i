<!-- include start from bgp/neighbor-capability.xml.i -->
<node name="capability">
  <properties>
    <help>Advertise capabilities to this peer-group</help>
  </properties>
  <children>
    <leafNode name="dynamic">
      <properties>
        <help>Advertise dynamic capability to this neighbor</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="extended-nexthop">
      <properties>
        <help>Advertise extended-nexthop capability to this neighbor</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="software-version">
      <properties>
        <help>Advertise Software Version capability to the peer</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
