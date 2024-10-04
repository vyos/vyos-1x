<!-- include start from firewall/set-packet-modifications-hop-limit.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="hop-limit">
      <properties>
        <help>Set hop limit</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Hop limit number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
