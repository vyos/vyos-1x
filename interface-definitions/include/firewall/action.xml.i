<!-- include start from firewall/action.xml.i -->
<leafNode name="action">
  <properties>
    <help>Rule action</help>
    <completionHelp>
<<<<<<< HEAD
      <list>accept jump reject return drop queue</list>
=======
      <list>accept continue jump reject return drop queue synproxy</list>
>>>>>>> bdad4e046 (T5217: Add firewall synproxy)
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
    <valueHelp>
      <format>queue</format>
      <description>Enqueue packet to userspace</description>
    </valueHelp>
    <valueHelp>
      <format>synproxy</format>
      <description>Synproxy connections</description>
    </valueHelp>
    <constraint>
<<<<<<< HEAD
      <regex>(accept|jump|reject|return|drop|queue)</regex>
=======
      <regex>(accept|continue|jump|reject|return|drop|queue|synproxy)</regex>
>>>>>>> bdad4e046 (T5217: Add firewall synproxy)
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
