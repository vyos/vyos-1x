<!-- include start from firewall/default-action.xml.i -->
<leafNode name="default-action">
  <properties>
    <help>Default-action for rule-set</help>
    <completionHelp>
      <list>drop jump reject accept</list>
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
      <format>reject</format>
      <description>Drop and notify source if no prior rules are hit</description>
    </valueHelp>
    <valueHelp>
      <format>accept</format>
      <description>Accept if no prior rules are hit</description>
    </valueHelp>
    <constraint>
      <regex>(drop|jump|reject|accept)</regex>
    </constraint>
  </properties>
  <defaultValue>drop</defaultValue>
</leafNode>
<!-- include end -->
