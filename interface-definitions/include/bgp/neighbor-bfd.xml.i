<!-- include start from bgp/neighbor-bfd.xml.i -->
<node name="bfd">
  <properties>
    <help>Enable Bidirectional Forwarding Detection (BFD) support</help>
  </properties>
  <children>
    #include <include/bfd/profile.xml.i>
    <leafNode name="check-control-plane-failure">
      <properties>
        <help>Allow to write CBIT independence in BFD outgoing packets and read both C-BIT value of BFD and lookup BGP peer status</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="strict">
      <properties>
        <help>Strict mode</help>
      </properties>
      <children>
        <leafNode name="hold-time">
          <properties>
            <help>BFD hold time</help>
            <valueHelp>
              <format>u32:1-4294967295</format>
              <description>BFD hold time in seconds</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-4294967295"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
