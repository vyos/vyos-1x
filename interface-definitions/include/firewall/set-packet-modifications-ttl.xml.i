<!-- include start from firewall/set-packet-modifications-ttl.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="ttl">
      <properties>
        <help>Set TTL (time to live)</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>TTL number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
