<!-- include start from accel-ppp/shaper.xml.i -->
<node name="shaper">
  <properties>
    <help>Traffic shaper bandwidth parameters</help>
  </properties>
  <children>
    <leafNode name="fwmark">
      <properties>
        <help>Firewall mark value for traffic that excludes from shaping</help>
        <valueHelp>
          <format>u32:1-2147483647</format>
          <description>Match firewall mark value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
