<!-- include start from bgp/afi-redistribute-common-protocols.xml.i -->
<node name="babel">
  <properties>
    <help>Redistribute Babel routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<node name="connected">
  <properties>
    <help>Redistribute connected routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<node name="isis">
  <properties>
    <help>Redistribute IS-IS routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<node name="kernel">
  <properties>
    <help>Redistribute kernel routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<node name="nhrp">
  <properties>
    <help>Redistribute NHRP routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<node name="static">
  <properties>
    <help>Redistribute static routes into BGP</help>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</node>
<tagNode name="table">
  <properties>
    <help>Redistribute non-main Kernel Routing Table</help>
    <completionHelp>
      <path>protocols static table</path>
    </completionHelp>
    #include <include/constraint/protocols-static-table.xml.i>
  </properties>
  <children>
    #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
  </children>
</tagNode>
<!-- include end -->
