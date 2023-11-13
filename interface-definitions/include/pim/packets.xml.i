<!-- include start from pim/packets.xml.i -->
<leafNode name="packets">
  <properties>
    <help>Packets to process at once</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Number of packets</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
  <defaultValue>3</defaultValue>
</leafNode>
<!-- include end -->
