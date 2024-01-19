<!-- include start from firewall/synproxy.xml.i -->
<node name="synproxy">
  <properties>
    <help>Synproxy options</help>
  </properties>
  <children>
    <node name="tcp">
      <properties>
        <help>TCP synproxy options</help>
      </properties>
      <children>
        <leafNode name="mss">
          <properties>
            <help>TCP Maximum segment size</help>
            <valueHelp>
              <format>u32:501-65535</format>
              <description>Maximum segment size for synproxy connections</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 501-65535"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="window-scale">
          <properties>
            <help>TCP window scale for synproxy connections</help>
            <valueHelp>
              <format>u32:1-14</format>
              <description>TCP window scale</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-14"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
