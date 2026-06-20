<!-- include start from vpn-ipsec-esn.xml.i -->
<leafNode name="esn">
  <properties>
    <help>Extended Sequence Number (ESN)</help>
    <completionHelp>
      <list>optional required disabled</list>
    </completionHelp>
    <valueHelp>
      <format>optional</format>
      <description>Prefer ESN, but allow 32-bit sequence numbers</description>
    </valueHelp>
    <valueHelp>
      <format>required</format>
      <description>ESN enabled, accept 64-bit sequence numbers only</description>
    </valueHelp>
    <valueHelp>
      <format>disabled</format>
      <description>ESN disabled, accept 32-bit sequence numbers only</description>
    </valueHelp>
    <constraint>
      <regex>(optional|required|disabled)</regex>
    </constraint>
  </properties>
  <defaultValue>disabled</defaultValue>
</leafNode>
<!-- include end -->
