<!-- include start from firewall/match-vlan.xml.i -->
<node name="vlan">
  <properties>
    <help>VLAN parameters</help>
  </properties>
  <children>
    <leafNode name="id">
      <properties>
        <help>VLAN id</help>
        <valueHelp>
          <format>u32:0-4096</format>
          <description>VLAN id</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;start-end&gt;</format>
          <description>VLAN id range to match</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 0-4095"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="priority">
      <properties>
        <help>VLAN priority(pcp)</help>
        <valueHelp>
          <format>u32:0-7</format>
          <description>VLAN priority</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;start-end&gt;</format>
          <description>VLAN priority range to match</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 0-7"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->