<!-- include start from firewall/hop-limit.xml.i -->
<node name="hop-limit">
  <properties>
    <help>Hop limit</help>
  </properties>
  <children>
    #include <include/firewall/eq.xml.i>
    #include <include/firewall/gt.xml.i>
    #include <include/firewall/lt.xml.i>
  </children>
</node>
<!-- include end -->