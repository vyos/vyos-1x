<!-- include start from qos/mtu.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>MTU size for this class</help>
    <valueHelp>
      <format>u32:256-65535</format>
      <description>Bytes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 256-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
