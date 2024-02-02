<!-- include start from accel-ppp/ppp-options.xml.i -->
<node name="ppp-options">
  <properties>
    <help>Advanced protocol options</help>
  </properties>
  <children>
    <leafNode name="min-mtu">
      <properties>
        <help>Minimum acceptable MTU (68-65535)</help>
        <constraint>
          <validator name="numeric" argument="--range 68-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="mru">
      <properties>
        <help>Preferred MRU (68-65535)</help>
        <constraint>
          <validator name="numeric" argument="--range 68-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="disable-ccp">
      <properties>
        <help>Disable Compression Control Protocol (CCP)</help>
        <valueless />
      </properties>
    </leafNode>
    #include <include/accel-ppp/ppp-mppe.xml.i>
    #include <include/accel-ppp/lcp-echo-interval-failure.xml.i>
    #include <include/accel-ppp/lcp-echo-timeout.xml.i>
    #include <include/accel-ppp/ppp-interface-cache.xml.i>
    <leafNode name="ipv4">
      <properties>
        <help>IPv4 (IPCP) negotiation algorithm</help>
        <constraint>
          <regex>(deny|allow|prefer|require)</regex>
        </constraint>
        <constraintErrorMessage>invalid value</constraintErrorMessage>
        <valueHelp>
          <format>deny</format>
          <description>Do not negotiate IPv4</description>
        </valueHelp>
        <valueHelp>
          <format>allow</format>
          <description>Negotiate IPv4 only if client requests</description>
        </valueHelp>
        <valueHelp>
          <format>prefer</format>
          <description>Ask client for IPv4 negotiation, do not fail if it rejects</description>
        </valueHelp>
        <valueHelp>
          <format>require</format>
          <description>Require IPv4 negotiation</description>
        </valueHelp>
        <completionHelp>
          <list>deny allow prefer require</list>
        </completionHelp>
      </properties>
    </leafNode>
    #include <include/accel-ppp/ppp-options-ipv6.xml.i>
    #include <include/accel-ppp/ppp-options-ipv6-interface-id.xml.i>
  </children>
</node>
<!-- include end -->
