<!-- include start from bgp/neighbor-bfd.xml.i -->
<node name="bfd">
  <properties>
    <help>Enable Bidirectional Forwarding Detection (BFD) support</help>
  </properties>
  <children>
    <leafNode name="check-control-plane-failure">
      <properties>
        <help>Allow to write CBIT independence in BFD outgoing packets and read both C-BIT value of BFD and lookup BGP peer status</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
