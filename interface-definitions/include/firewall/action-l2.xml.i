<!-- include start from firewall/action.xml.i -->
<leafNode name="action">
  <properties>
    <help>Rule action</help>
    <completionHelp>
      <list>accept continue jump return drop queue</list>
    </completionHelp>
    <valueHelp>
      <format>accept</format>
      <description>Accept matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>continue</format>
      <description>Continue parsing next rule</description>
    </valueHelp>
    <valueHelp>
      <format>jump</format>
      <description>Jump to another chain</description>
    </valueHelp>
    <valueHelp>
      <format>return</format>
      <description>Return from the current chain and continue at the next rule of the last chain</description>
    </valueHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>queue</format>
      <description>Enqueue packet to userspace</description>
    </valueHelp>
    <constraint>
      <regex>(accept|continue|jump|return|drop|queue)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
