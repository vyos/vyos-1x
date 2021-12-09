<!-- include start from bgp/neighbor-bfd.xml.i -->
<node name="bfd">
  <properties>
    <help>Enable Bidirectional Forwarding Detection (BFD) support</help>
  </properties>
  <children>
    #include <include/bfd/profile.xml.i>
    <leafNode name="check-control-plane-failure">
      <properties>
        <help>Allow to write CBIT independence in BFD outgoing packets and read both C-BIT value of BFD and lookup BGP peer status</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
