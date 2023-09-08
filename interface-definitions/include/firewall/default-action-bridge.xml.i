<!-- include start from firewall/default-action.xml.i -->
<leafNode name="default-action">
  <properties>
    <help>Default-action for rule-set</help>
    <completionHelp>
      <list>drop jump return accept continue</list>
    </completionHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop if no prior rules are hit</description>
    </valueHelp>
    <valueHelp>
      <format>jump</format>
      <description>Jump to another chain if no prior rules are hit</description>
    </valueHelp>
    <valueHelp>
      <format>return</format>
      <description>Return from the current chain and continue at the next rule of the last chain</description>
    </valueHelp>
    <valueHelp>
      <format>accept</format>
      <description>Accept if no prior rules are hit</description>
    </valueHelp>
    <valueHelp>
      <format>continue</format>
      <description>Continue parsing next rule</description>
    </valueHelp>
    <constraint>
      <regex>(drop|jump|return|accept|continue)</regex>
    </constraint>
  </properties>
  <defaultValue>drop</defaultValue>
</leafNode>
<!-- include end -->
