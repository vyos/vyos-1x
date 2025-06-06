<!-- include start from serial/general/packet-forwarding.xml.i -->
<node name="packet-forwarding">
  <properties>
    <help>Packet forwarding setting</help>
  </properties>
  <children>
    <leafNode name="mode">
      <properties>
        <help>Packet forwarding mode</help>
        <completionHelp>
          <list>minimize-latency optimize-network-throughput prevent-message-fragmentation custom</list>
        </completionHelp>
        <constraint>
          <regex>(minimize-latency|optimize-network-throughput|prevent-message-fragmentation|custom)</regex>
        </constraint>
      </properties>
      <defaultValue>minimize-latency</defaultValue>
    </leafNode>
    <leafNode name="delay-between-messages">
      <properties>
        <help>Delay sending between messages</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Packet Size in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="forwarding-rule">
      <properties>
        <help>Forwarding Rule</help>
        <completionHelp>
          <list>strip-trigger trigger trigger+1 trigger+2</list>
        </completionHelp>
        <valueHelp>
          <format>strip-trigger</format>
          <description>Strips out the EOF1, EOF1/EOF2, Trigger1, or Trigger1/Trigger2, depending on your settings</description>
        </valueHelp>
        <valueHelp>
          <format>trigger</format>
          <description>Includes the EOF1, EOF1/EOF2, Trigger1, or Trigger1/Trigger2, depending on your settings</description>
        </valueHelp>
        <valueHelp>
          <format>trigger+1</format>
          <description>Includes the EOF1, EOF1/EOF2, Trigger1, or Trigger1/Trigger2, depending on your settings, plus the first byte that follows the trigger</description>
        </valueHelp>
        <valueHelp>
          <format>trigger+2</format>
          <description>Trigger+2—Includes the EOF1, EOF1/EOF2, Trigger1, or Trigger1/Trigger2, depending on your settings, plus the next two bytes received after the trigger</description>
        </valueHelp>
        <constraint>
          <regex>(strip-trigger|trigger|trigger+1|trigger+2)</regex>
        </constraint>
      </properties>
      <defaultValue>trigger</defaultValue>
    </leafNode>
    <leafNode name="start-of-frame-value1">
      <properties>
        <help>Start of frame first hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>Start of frame first char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="end-of-frame-value1">
      <properties>
        <help>End of frame first hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>End of frame first char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="start-of-frame-value2">
      <properties>
        <help>Start of frame second hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>Start of frame second char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="end-of-frame-value2">
      <properties>
        <help>End of frame second hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>End of frame second char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="start-frame-transmit">
      <properties>
        <help>Enable transmit Start of Frame Character(s)</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="packet-size">
      <properties>
        <help>Packet Size</help>
        <valueHelp>
          <format>u32:0-1024</format>
          <description>Packet Size in bytes</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-1024"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="idle-timer">
      <properties>
        <help>Idle Timer</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Idle Timer in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="force-transmit-timer">
      <properties>
        <help>Force Transmit Timer</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Force Transmit Timer in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="end-trigger-value1">
      <properties>
        <help>End Trigger first hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>End trigger 1 char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="end-trigger-value2">
      <properties>
        <help>End Trigger second hex value</help>
        <valueHelp>
          <format>txt</format>
          <description>End trigger 2 char</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
