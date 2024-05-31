<!-- include start from qos/class-match-ipv6.xml.i -->
<node name="ipv6">
  <properties>
    <help>Match IPv6 protocol header</help>
  </properties>
  <children>
    <node name="destination">
      <properties>
        <help>Match on destination port or address</help>
      </properties>
      <children>
        #include <include/qos/class-match-ipv6-address.xml.i>
        #include <include/port-number.xml.i>
      </children>
    </node>
    #include <include/qos/match-dscp.xml.i>
    #include <include/qos/max-length.xml.i>
    #include <include/ip-protocol.xml.i>
    <node name="source">
      <properties>
        <help>Match on source port or address</help>
      </properties>
      <children>
        #include <include/qos/class-match-ipv6-address.xml.i>
        #include <include/port-number.xml.i>
      </children>
    </node>
    #include <include/qos/tcp-flags.xml.i>
  </children>
</node>
<!-- include end -->
