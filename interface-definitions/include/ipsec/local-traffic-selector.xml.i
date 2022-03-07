<!-- include start from ipsec/local-traffic-selector.xml.i -->
<node name="local">
  <properties>
    <help>Local parameters for interesting traffic</help>
  </properties>
  <children>
    #include <include/port-number.xml.i>
    <leafNode name="prefix">
      <properties>
        <help>Local IPv4 or IPv6 prefix</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>Local IPv4 prefix</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6net</format>
          <description>Local IPv6 prefix</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
          <validator name="ipv6-prefix"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
