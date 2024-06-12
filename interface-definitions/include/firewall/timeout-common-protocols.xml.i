<!-- include start from firewall/timeout-common-protocols.xml.i -->
<leafNode name="icmp">
  <properties>
    <help>ICMP timeout in seconds</help>
    <valueHelp>
      <format>u32:1-21474836</format>
      <description>ICMP timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-21474836"/>
    </constraint>
  </properties>
  <defaultValue>30</defaultValue>
</leafNode>
<leafNode name="other">
  <properties>
    <help>Generic connection timeout in seconds</help>
    <valueHelp>
      <format>u32:1-21474836</format>
      <description>Generic connection timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-21474836"/>
    </constraint>
  </properties>
  <defaultValue>600</defaultValue>
</leafNode>
<node name="tcp">
  <properties>
    <help>TCP connection timeout options</help>
  </properties>
  <children>
    <leafNode name="close-wait">
      <properties>
        <help>TCP CLOSE-WAIT timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP CLOSE-WAIT timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>60</defaultValue>
    </leafNode>
    <leafNode name="close">
      <properties>
        <help>TCP CLOSE timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP CLOSE timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>10</defaultValue>
    </leafNode>
    <leafNode name="established">
      <properties>
        <help>TCP ESTABLISHED timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP ESTABLISHED timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>432000</defaultValue>
    </leafNode>
    <leafNode name="fin-wait">
      <properties>
        <help>TCP FIN-WAIT timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP FIN-WAIT timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>120</defaultValue>
    </leafNode>
    <leafNode name="last-ack">
      <properties>
        <help>TCP LAST-ACK timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP LAST-ACK timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>30</defaultValue>
    </leafNode>
    <leafNode name="syn-recv">
      <properties>
        <help>TCP SYN-RECEIVED timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP SYN-RECEIVED timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>60</defaultValue>
    </leafNode>
    <leafNode name="syn-sent">
      <properties>
        <help>TCP SYN-SENT timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP SYN-SENT timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>120</defaultValue>
    </leafNode>
    <leafNode name="time-wait">
      <properties>
        <help>TCP TIME-WAIT timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>TCP TIME-WAIT timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>120</defaultValue>
    </leafNode>
  </children>
</node>
<node name="udp">
  <properties>
    <help>UDP timeout options</help>
  </properties>
  <children>
    <leafNode name="other">
      <properties>
        <help>UDP generic timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>UDP generic timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>30</defaultValue>
    </leafNode>
    <leafNode name="stream">
      <properties>
        <help>UDP stream timeout in seconds</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>UDP stream timeout in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
      <defaultValue>180</defaultValue>
    </leafNode>
  </children>
</node>
