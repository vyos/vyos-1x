<!-- include start from firewall/icmp.xml.i -->
<node name="icmp">
  <properties>
    <help>ICMP type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMP code</help>
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
        <help>ICMP type</help>
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