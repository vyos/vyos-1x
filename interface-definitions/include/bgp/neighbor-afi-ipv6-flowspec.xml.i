<!-- include start from bgp/neighbor-afi-ipv6-flowspec.xml.i -->
<node name="ipv6-flowspec">
  <properties>
    <help>IPv6 Flow Specification BGP neighbor parameters</help>
  </properties>
  <children>
    #include <include/bgp/afi-ipv6-prefix-list.xml.i>
    #include <include/bgp/afi-common-flowspec.xml.i>
  </children>
</node>
<!-- include end -->
