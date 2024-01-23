<!-- include start from bfd/common.xml.i -->
<leafNode name="echo-mode">
  <properties>
    <help>Enables the echo transmission mode</help>
    <valueless/>
  </properties>
</leafNode>
<node name="interval">
  <properties>
    <help>Configure timer intervals</help>
  </properties>
  <children>
    <leafNode name="receive">
      <properties>
        <help>Minimum interval of receiving control packets</help>
        <valueHelp>
          <format>u32:10-60000</format>
          <description>Interval in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-60000"/>
        </constraint>
      </properties>
      <defaultValue>300</defaultValue>
    </leafNode>
    <leafNode name="transmit">
      <properties>
        <help>Minimum interval of transmitting control packets</help>
        <valueHelp>
          <format>u32:10-60000</format>
          <description>Interval in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-60000"/>
        </constraint>
      </properties>
      <defaultValue>300</defaultValue>
    </leafNode>
    <leafNode name="multiplier">
      <properties>
        <help>Multiplier to determine packet loss</help>
        <valueHelp>
          <format>u32:2-255</format>
          <description>Remote transmission interval will be multiplied by this value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 2-255"/>
        </constraint>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="echo-interval">
      <properties>
        <help>Echo receive transmission interval</help>
        <valueHelp>
          <format>u32:10-60000</format>
          <description>The minimal echo receive transmission interval that this system is capable of handling</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-60000"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="minimum-ttl">
  <properties>
    <help>Expect packets with at least this TTL</help>
    <valueHelp>
      <format>u32:1-254</format>
      <description>Minimum TTL expected</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-254"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="passive">
  <properties>
    <help>Do not attempt to start sessions</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="shutdown">
  <properties>
    <help>Disable this peer</help>
    <valueless/>
  </properties>
</leafNode>
<!-- include end -->
