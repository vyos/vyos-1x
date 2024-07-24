<!-- include start from firewall/set-packet-modifications.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="connection-mark">
      <properties>
        <help>Connection marking</help>
        <valueHelp>
          <format>u32:0-2147483647</format>
          <description>Connection marking</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="dscp">
      <properties>
        <help>Packet Differentiated Services Codepoint (DSCP)</help>
        <valueHelp>
          <format>u32:0-63</format>
          <description>DSCP number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-63"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="mark">
      <properties>
        <help>Packet marking</help>
        <valueHelp>
          <format>u32:1-2147483647</format>
          <description>Packet marking</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="table">
      <properties>
        <help>Routing table to forward packet with</help>
        <valueHelp>
          <format>u32:1-200</format>
          <description>Table number</description>
        </valueHelp>
        <valueHelp>
          <format>main</format>
          <description>Main table</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-200"/>
          <regex>(main)</regex>
        </constraint>
        <completionHelp>
          <list>main</list>
          <path>protocols static table</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="tcp-mss">
      <properties>
        <help>TCP Maximum Segment Size</help>
        <valueHelp>
          <format>u32:500-1460</format>
          <description>Explicitly set TCP MSS value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 500-1460"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->