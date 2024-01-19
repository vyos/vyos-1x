<!-- include start from firewall/match-vlan.xml.i -->
<node name="vlan">
  <properties>
    <help>VLAN parameters</help>
  </properties>
  <children>
    <leafNode name="id">
      <properties>
        <help>Vlan id</help>
        <valueHelp>
          <format>u32:0-4096</format>
          <description>Vlan id</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;start-end&gt;</format>
          <description>Vlan id range to match</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 0-4095"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="priority">
      <properties>
        <help>Vlan priority(pcp)</help>
        <valueHelp>
          <format>u32:0-7</format>
          <description>Vlan priority</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;start-end&gt;</format>
          <description>Vlan priority range to match</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 0-7"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->