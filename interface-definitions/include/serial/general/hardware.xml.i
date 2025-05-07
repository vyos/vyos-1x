<!-- include start from serial/general/hardware.xml.i -->
<node name="hardware">
  <properties>
    <help>Hardware setting</help>
  </properties>
  <children>
    <leafNode name="speed">
      <properties>
        <help>Baud rate</help>
        <completionHelp>
          <list>300 600 1200 1800 2400 4800 9600 19200 28800 38400 57600 115200 230400</list>
        </completionHelp>
        <constraint>
          <regex>(300|600|1200|1800|2400|4800|9600|19200|28800|38400|57600|115200|230400)</regex>
        </constraint>
      </properties>
      <defaultValue>9600</defaultValue>
    </leafNode>
    <leafNode name="flow-control">
      <properties>
        <help>Flow control</help>
        <completionHelp>
          <list>none soft hard both</list>
        </completionHelp>
        <constraint>
          <regex>(none|soft|hard|both)</regex>
        </constraint>
      </properties>
      <defaultValue>none</defaultValue>
    </leafNode>
    <leafNode name="data-bits">
      <properties>
        <help>Data bits</help>
        <completionHelp>
          <list>5 6 7 8</list>
        </completionHelp>
        <constraint>
          <regex>(5|6|7|8)</regex>
        </constraint>
      </properties>
      <defaultValue>8</defaultValue>
    </leafNode>
    <leafNode name="parity">
      <properties>
        <help>Parity</help>
        <completionHelp>
          <list>none odd even mark space</list>
        </completionHelp>
        <constraint>
          <regex>(none|odd|even|mark|space)</regex>
        </constraint>
      </properties>
      <defaultValue>none</defaultValue>
    </leafNode>
    <leafNode name="stop-bits">
      <properties>
        <help>Stop bits</help>
        <completionHelp>
          <list>1 2</list>
        </completionHelp>
        <constraint>
          <regex>(1|2)</regex>
        </constraint>
      </properties>
      <defaultValue>1</defaultValue>
    </leafNode>
    <leafNode name="monitor-dsr">
      <properties>
        <help>Enable DTR-DSR monitor</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="monitor-dcd">
      <properties>
        <help>Enable DCD monitor</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="flow-in">
      <properties>
        <help>Enable inbound flow control</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="flow-out">
      <properties>
        <help>Enable outbound flow control</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="rts-toggle">
      <properties>
        <help>Enable RTS Toggle if your application needs for RTS to be raised during character transmission</help>
      </properties>
      <children>
        <leafNode name="final-delay">
          <properties>
            <help>Time between the time of character transmission and when RTS is dropped (in ms, default: 0)</help>
            <valueHelp>
              <format>u32:0-1000</format>
              <description>Decimal integer (0 - 1000)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-1000"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="initial-delay">
          <properties>
            <help>Time between the time the RTS signal is raised and the start of character transmission (in ms, default: 0)</help>
            <valueHelp>
              <format>u32:0-1000</format>
              <description>Decimal integer (0 - 1000)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-1000"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
