<!-- include start from bgp/afi-default-originate.xml.i -->
<node name="default-originate">
  <properties>
    <help>Originate default route to this peer</help>
  </properties>
  <children>
    #include <include/route-map.xml.i>
  </children>
</node>
<!-- include end -->
