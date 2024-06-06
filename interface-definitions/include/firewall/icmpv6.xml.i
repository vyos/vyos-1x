<!-- include start from firewall/icmpv6.xml.i -->
<node name="icmpv6">
  <properties>
    <help>ICMPv6 type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMPv6 code</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMPv6 code (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="type">
      <properties>
        <help>ICMPv6 type</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMPv6 type (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/icmpv6-type-name.xml.i>
  </children>
</node>
<!-- include end -->