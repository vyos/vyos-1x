<!-- include start from stunnel/listen.xml.i -->
<node name="listen">
  <properties>
    <help>Accept connections on specified address</help>
  </properties>
  <children>
    #include <include/stunnel/address.xml.i>
    #include <include/port-number.xml.i>
  </children>
</node>
<!-- include end -->
