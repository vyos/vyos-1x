<!-- include start from conntrack/timeout-custom-protocols.xml.i -->
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
    </leafNode>
  </children>
</node>
<node name="udp">
  <properties>
    <help>UDP timeout options</help>
  </properties>
  <children>
    <leafNode name="replied">
      <properties>
        <help>Timeout for UDP connection seen in both directions</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>Timeout for UDP connection seen in both directions</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="unreplied">
      <properties>
        <help>Timeout for unreplied UDP</help>
        <valueHelp>
          <format>u32:1-21474836</format>
          <description>Timeout for unreplied UDP</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-21474836"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
