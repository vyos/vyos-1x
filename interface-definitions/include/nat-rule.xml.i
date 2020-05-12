<tagNode name="rule">
  <properties>
    <help>Rule number for NAT</help>
    <valueHelp>
      <format>1-9999</format>
      <description>Number for this NAT rule</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-9999"/>
    </constraint>
    <constraintErrorMessage>NAT rule number must be between 1 and 9999</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="description">
      <properties>
        <help>Rule description</help>
      </properties>
    </leafNode>
    <node name="destination">
      <properties>
        <help>NAT destination parameters</help>
      </properties>
      <children>
        #include <include/nat-address.xml.i>
        #include <include/nat-port.xml.i>
      </children>
    </node>
    <leafNode name="disable">
      <properties>
        <help>Disable NAT rule</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="exclude">
      <properties>
        <help>Exclude packets matching this rule from NAT</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="log">
      <properties>
        <help>NAT rule logging</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="protocol">
      <properties>
        <help>Protocol to NAT</help>
        <completionHelp>
          <list>tcp udp tcp_udp all</list>
        </completionHelp>
        <valueHelp>
          <format>tcp</format>
          <description>Transmission Control Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>udp</format>
          <description>User Datagram Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>tcp_udp</format>
          <description>Both TCP and UDP</description>
        </valueHelp>
        <valueHelp>
          <format>all</format>
          <description>All IP protocols</description>
        </valueHelp>
        <valueHelp>
          <format>0-255</format>
          <description>IP protocol number</description>
        </valueHelp>
        <valueHelp>
          <format>!&lt;protocol&gt;</format>
          <description>All IP protocols except for the specified name or number (negation)</description>
        </valueHelp>
      </properties>
    </leafNode>
    <node name="source">
      <properties>
        <help>NAT source parameters</help>
      </properties>
      <children>
        #include <include/nat-address.xml.i>
        #include <include/nat-port.xml.i>
      </children>
    </node>
  </children>
</tagNode>
