<!-- included start from monitor-ospf-packet-detail.xml.i -->
<node name="detail">
  <properties>
    <help>Enable detailed OSPF packet debugging</help>
  </properties>
  <command>vtysh -c "debug ospf ${@:3}"</command>
</node>
<node name="recv">
  <properties>
    <help>Enable OSPF recv packet debugging</help>
  </properties>
  <command>vtysh -c "debug ospf ${@:3}"</command>
  <children>
    <node name="detail">
      <properties>
        <help>Enable detailed OSPF recv packet debugging</help>
      </properties>
      <command>vtysh -c "debug ospf ${@:3}"</command>
    </node>
  </children>
</node>
<node name="send">
  <properties>
    <help>Enable OSPF send packet debugging</help>
  </properties>
  <command>vtysh -c "debug ospf ${@:3}"</command>
  <children>
    <node name="detail">
      <properties>
        <help>Enable detailed OSPF send packet debugging</help>
      </properties>
      <command>vtysh -c "debug ospf ${@:3}"</command>
    </node>
  </children>
</node>
<!-- included end -->
