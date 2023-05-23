<!-- include start from firewall/inbound-interface.xml.i -->
<node name="inbound-interface">
  <properties>
    <help>Match inbound-interface</help>
  </properties>
  <children>
    #include <include/firewall/match-interface.xml.i>
  </children>
</node>
<!-- include end -->