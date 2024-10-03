<!-- include start from firewall/set-packet-modifications-conn-mark.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="connection-mark">
      <properties>
        <help>Set connection mark</help>
        <valueHelp>
          <format>u32:0-2147483647</format>
          <description>Connection mark</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
