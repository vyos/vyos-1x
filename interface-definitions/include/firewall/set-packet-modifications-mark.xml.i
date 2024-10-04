<!-- include start from firewall/set-packet-modifications-mark.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="mark">
      <properties>
        <help>Set packet mark</help>
        <valueHelp>
          <format>u32:1-2147483647</format>
          <description>Packet mark</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
