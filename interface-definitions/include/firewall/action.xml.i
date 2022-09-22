<!-- include start from firewall/action.xml.i -->
<leafNode name="action">
  <properties>
    <help>Rule action</help>
    <completionHelp>
      <list>accept jump reject return drop</list>
    </completionHelp>
    <valueHelp>
      <format>accept</format>
      <description>Accept matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>jump</format>
      <description>Jump to another chain</description>
    </valueHelp>
    <valueHelp>
      <format>reject</format>
      <description>Reject matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>return</format>
      <description>Return from the current chain and continue at the next rule of the last chain</description>
    </valueHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop matching entries</description>
    </valueHelp>
    <constraint>
      <regex>(accept|jump|reject|return|drop)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
