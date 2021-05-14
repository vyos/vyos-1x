<!-- include start from bgp/neighbor-afi-ipv4-flowspec.xml.i -->
<node name="ipv4-flowspec">
  <properties>
    <help>IPv4 Flow Specification BGP neighbor parameters</help>
  </properties>
  <children>
    #include <include/bgp/afi-ipv4-prefix-list.xml.i>
    #include <include/bgp/afi-common-flowspec.xml.i>
  </children>
</node>
<!-- include end -->
