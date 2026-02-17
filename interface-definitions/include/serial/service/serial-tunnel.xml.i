<!-- include start from serial/service/serial-tunnel.xml.i -->
<node name="serial-tunnel">
  <properties>
    <help>Serial tunnel profile</help>
  </properties>
  <children>
    <leafNode name="break-length">
      <properties>
        <help>The length of time the break condition will be asserted when received a break signal</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Specifies the length in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
      <defaultValue>1000</defaultValue>
    </leafNode>
    <leafNode name="mode">
      <properties>
        <help>Serial tunnel mode</help>
        <completionHelp>
          <list>client server</list>
        </completionHelp>
        <constraint>
          <regex>(client|server)</regex>
        </constraint>
      </properties>
      <defaultValue>server</defaultValue>
    </leafNode>
    <node name="client">
      <properties>
        <help>Client setting</help>
      </properties>
      <children>
        #include <include/serial/service/utils/host-info.xml.i>
      </children>
    </node>
    <leafNode name="delay-after-break">
      <properties>
        <help>The delay between the termination of a a break condition and the time data will be sent</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Specifies the delay in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
