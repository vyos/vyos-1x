<!-- include start from ospf/auto-cost.xml.i -->
<node name="auto-cost">
  <properties>
    <help>Calculate interface cost according to bandwidth</help>
  </properties>
  <children>
    <leafNode name="reference-bandwidth">
      <properties>
        <help>Reference bandwidth method to assign cost</help>
        <valueHelp>
          <format>u32:1-4294967</format>
          <description>Reference bandwidth cost in Mbits/sec</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-4294967"/>
        </constraint>
      </properties>
      <defaultValue>100</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
