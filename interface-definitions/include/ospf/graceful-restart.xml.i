<!-- include start from ospf/graceful-restart.xml.i -->
<node name="graceful-restart">
  <properties>
    <help>Graceful Restart</help>
  </properties>
  <children>
    <leafNode name="grace-period">
      <properties>
        <help>Maximum length of the grace period</help>
        <valueHelp>
          <format>u32:1-1800</format>
          <description>Maximum length of the grace period in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 5-1800"/>
        </constraint>
      </properties>
      <defaultValue>120</defaultValue>
    </leafNode>
    <node name="helper">
      <properties>
        <help>OSPF graceful-restart helpers</help>
      </properties>
      <children>
        <node name="enable">
          <properties>
            <help>Enable helper support</help>
          </properties>
          <children>
            <leafNode name="router-id">
              <properties>
                <help>Advertising Router-ID</help>
                <valueHelp>
                  <format>ipv4</format>
                  <description>Router-ID in IP address format</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4-address"/>
                </constraint>
                <multi/>
              </properties>
            </leafNode>
          </children>
        </node>
        <leafNode name="planned-only">
          <properties>
            <help>Supported only planned restart</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="supported-grace-time">
          <properties>
            <help>Supported grace timer</help>
            <valueHelp>
              <format>u32:10-1800</format>
              <description>Grace interval in seconds</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 10-1800"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
