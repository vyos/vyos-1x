<!-- included start from ospf-interface-common.xml.i -->
<leafNode name="bfd">
  <properties>
    <help>Enable Bidirectional Forwarding Detection (BFD) support</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="cost">
  <properties>
    <help>Interface cost</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>OSPF interface cost</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="mtu-ignore">
  <properties>
    <help>Disable Maximum Transmission Unit (MTU) mismatch detection</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="priority">
  <properties>
    <help>Router priority (default: 1)</help>
    <valueHelp>
      <format>u32:0-255</format>
      <description>OSPF router priority cost</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
  </properties>
  <defaultValue>1</defaultValue>
</leafNode>
<!-- included end -->
