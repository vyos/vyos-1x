<!-- include start from firewall/set-packet-modifications-dscp.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="dscp">
      <properties>
        <help>Set DSCP (Packet Differentiated Services Codepoint) bits</help>
        <valueHelp>
          <format>u32:0-63</format>
          <description>DSCP number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-63"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
