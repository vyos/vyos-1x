<!-- include start from bgp/neighbor-bfd.xml.i -->
<node name="bfd">
  <properties>
    <help>Enable Bidirectional Forwarding Detection (BFD) support</help>
  </properties>
  <children>
    #include <include/bfd/profile.xml.i>
    <node name="strict">
      <properties>
        <help>Do not allow BGP to establish a connection with the peer until the BFD session is up</help>
      </properties>
      <children>
        <leafNode name="hold-time">
          <properties>
            <help>Wait for the hold-time to expire before close BGP session</help>
            <valueHelp>
              <format>u32:0-86400</format>
              <description>Hold time in seconds</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-86400"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="check-control-plane-failure">
      <properties>
        <help>Allow to write CBIT independence in BFD outgoing packets and read both C-BIT value of BFD and lookup BGP peer status</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
