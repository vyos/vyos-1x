<!-- include start from firewall/fib.xml.i -->
<node name="fib">
  <properties>
    <help>Match based on the result of a Forwarding Information Base (FIB) lookup</help>
  </properties>
  <children>
    <leafNode name="type">
      <properties>
        <help>Match based on the address type returned by a FIB lookup</help>
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
<!-- include end -->
