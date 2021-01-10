<!-- included start from monitor-ospf-packet-detail.xml.i -->
<node name="detail">
  <properties>
    <help>Disable detailed OSPF packet debugging</help>
  </properties>
  <command>vtysh -c "no debug ospf ${@:3}"</command>
</node>
<node name="recv">
  <properties>
    <help>Disable OSPF recv packet debugging</help>
  </properties>
  <command>vtysh -c "no debug ospf ${@:3}"</command>
  <children>
    <node name="detail">
      <properties>
        <help>Disable detailed OSPF recv packet debugging</help>
      </properties>
      <command>vtysh -c "no debug ospf ${@:3}"</command>
    </node>
  </children>
</node>
<node name="send">
  <properties>
    <help>Disable OSPF send packet debugging</help>
  </properties>
  <command>vtysh -c "no debug ospf ${@:3}"</command>
  <children>
    <node name="detail">
      <properties>
        <help>Disable detailed OSPF send packet debugging</help>
      </properties>
      <command>vtysh -c "no debug ospf ${@:3}"</command>
    </node>
  </children>
</node>
<!-- included end -->
