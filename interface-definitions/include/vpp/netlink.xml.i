<!-- include start from vpp/netlink.xml.i -->
<node name="netlink">
  <properties>
    <help>Netlink options</help>
  </properties>
  <children>
   <leafNode name="rx-buffer-size">
    <properties>
      <help>Receive buffer size</help>
      <valueHelp>
        <format>u32:0-4294967295</format>
        <description>Receive buffer size</description>
      </valueHelp>
      <constraint>
        <validator name="numeric" argument="--range 0-4294967295"/>
      </constraint>
    </properties>
  </leafNode>
  <leafNode name="batch-size">
    <properties>
      <help>Batch size</help>
      <valueHelp>
        <format>u32:0-4294967295</format>
        <description>Batch size</description>
      </valueHelp>
      <constraint>
        <validator name="numeric" argument="--range 0-4294967295"/>
      </constraint>
    </properties>
  </leafNode>
  <leafNode name="batch-delay-ms">
    <properties>
      <help>Batch delay</help>
      <valueHelp>
        <format>u32:0-4294967295</format>
        <description>Batch delay (in ms)</description>
      </valueHelp>
      <constraint>
        <validator name="numeric" argument="--range 0-4294967295"/>
      </constraint>
    </properties>
  </leafNode>
</children>
</node>
<!-- include end -->
