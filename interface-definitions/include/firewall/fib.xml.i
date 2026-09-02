<!-- include start from firewall/fib.xml.i -->
<node name="fib">
  <properties>
    <help>Match based on the result of a Forwarding Information Base (FIB) lookup</help>
  </properties>
  <children>
    <leafNode name="lookup">
      <properties>
        <help>Key to use for the FIB lookup</help>
        <completionHelp>
          <list>source-address destination-address</list>
        </completionHelp>
        <valueHelp>
          <format>source-address</format>
          <description>Look up a route to the packet's source address (reverse path)</description>
        </valueHelp>
        <valueHelp>
          <format>destination-address</format>
          <description>Look up a route to the packet's destination address</description>
        </valueHelp>
        <constraint>
          <regex>(source-address|destination-address)</regex>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <node name="match">
      <properties>
        <help>FIB lookup result to match against</help>
      </properties>
      <children>
        <leafNode name="route-type">
          <properties>
            <help>Match based on the address type returned by the FIB lookup</help>
            <completionHelp>
              <list>local unicast broadcast multicast anycast blackhole unreachable prohibit</list>
            </completionHelp>
            <valueHelp>
              <format>local</format>
              <description>Address is local to this router</description>
            </valueHelp>
            <valueHelp>
              <format>unicast</format>
              <description>Address is a unicast address</description>
            </valueHelp>
            <valueHelp>
              <format>broadcast</format>
              <description>Address is a broadcast address</description>
            </valueHelp>
            <valueHelp>
              <format>multicast</format>
              <description>Address is a multicast address</description>
            </valueHelp>
            <valueHelp>
              <format>anycast</format>
              <description>Address is an anycast address</description>
            </valueHelp>
            <valueHelp>
              <format>blackhole</format>
              <description>Address is blackholed</description>
            </valueHelp>
            <valueHelp>
              <format>unreachable</format>
              <description>Address is unreachable</description>
            </valueHelp>
            <valueHelp>
              <format>prohibit</format>
              <description>Address is administratively prohibited</description>
            </valueHelp>
            <constraint>
              <regex>(!?(local|unicast|broadcast|multicast|anycast|blackhole|unreachable|prohibit))</regex>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
