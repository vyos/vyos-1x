<!-- include start from firewall/action-map.xml.i -->
<leafNode name="action">
  <properties>
    <help>Rule action</help>
    <completionHelp>
      <list>accept continue drop goto jump return</list>
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
      <format>drop</format>
      <description>Drop matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>goto</format>
      <description>Go to another chain</description>
    </valueHelp>
    <valueHelp>
      <format>jump</format>
      <description>Jump to another chain</description>
    </valueHelp>
    <valueHelp>
      <format>return</format>
      <description>Return from the current chain and continue at the next rule of the last chain</description>
    </valueHelp>
    <constraint>
      <regex>(accept|continue|drop|goto|jump|return)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
