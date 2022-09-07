<!-- include start from firewall/ttl.xml.i -->
<node name="ttl">
  <properties>
    <help>Time to live limit</help>
  </properties>
  <children>
    #include <include/firewall/eq.xml.i>
    #include <include/firewall/gt.xml.i>
    #include <include/firewall/lt.xml.i>
  </children>
</node>
<!-- include end -->