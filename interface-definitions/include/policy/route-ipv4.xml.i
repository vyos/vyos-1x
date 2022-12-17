<!-- include start from policy/route-ipv4.xml.i -->
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
  </children>
</node>
<node name="icmp">
  <properties>
    <help>ICMP type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMP code (0-255)</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP code (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="type">
      <properties>
        <help>ICMP type (0-255)</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP type (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/icmp-type-name.xml.i>
  </children>
</node>
<!-- include end -->
