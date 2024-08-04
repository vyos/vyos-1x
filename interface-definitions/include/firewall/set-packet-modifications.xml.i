<!-- include start from firewall/set-packet-modifications.xml.i -->
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="connection-mark">
      <properties>
        <help>Set connection mark</help>
        <valueHelp>
          <format>u32:0-2147483647</format>
          <description>Connection mark</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="dscp">
      <properties>
        <help>Set DSCP (Packet Differentiated Services Codepoint) bits</help>
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
        <help>Set packet mark</help>
        <valueHelp>
          <format>u32:1-2147483647</format>
          <description>Packet mark</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="table">
      <properties>
        <help>Set the routing table for matched packets</help>
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
    <leafNode name="vrf">
      <properties>
        <help>VRF to forward packet with</help>
        <valueHelp>
          <format>txt</format>
          <description>VRF instance name</description>
        </valueHelp>
        <valueHelp>
          <format>default</format>
          <description>Forward into default global VRF</description>
        </valueHelp>
        <completionHelp>
          <list>default</list>
          <path>vrf name</path>
        </completionHelp>
        #include <include/constraint/vrf.xml.i>
      </properties>
    </leafNode>
    <leafNode name="tcp-mss">
      <properties>
        <help>Set TCP Maximum Segment Size</help>
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