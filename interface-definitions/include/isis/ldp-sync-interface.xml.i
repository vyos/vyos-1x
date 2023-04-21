<!-- include start from isis/ldp-igp-sync.xml.i -->
<node name="ldp-sync">
  <properties>
    <help>LDP-IGP synchronization configuration for interface</help>
  </properties>
  <children>
    #include <include/generic-disable-node.xml.i>
    #include <include/isis/ldp-sync-holddown.xml.i>
  </children>
</node>
<!-- include end -->
