<!-- include start from haproxy/timeout.xml.i -->
<node name="timeout">
  <properties>
    <help>Timeout options</help>
  </properties>
  <children>
    #include <include/haproxy/timeout-check.xml.i>
    #include <include/haproxy/timeout-connect.xml.i>
    #include <include/haproxy/timeout-server.xml.i>
  </children>
</node>
<!-- include end -->
