<!-- include start from ospf/retransmit-window.xml.i -->
<leafNode name="retransmit-window">
  <properties>
    <help>Window for LSA retransmit</help>
    <valueHelp>
      <format>u32:20-1000</format>
      <description>Retransmit LSAs expiring in this window (milliseconds)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 20-1000"/>
    </constraint>
  </properties>
  <defaultValue>50</defaultValue>
</leafNode>
<!-- include end -->
