<!-- include start from firewall/default-action-base-chains.xml.i -->
<leafNode name="default-action">
  <properties>
    <help>Default-action for rule-set</help>
    <completionHelp>
      <list>drop accept</list>
    </completionHelp>
    <valueHelp>
      <format>drop</format>
      <description>Drop if no prior rules are hit</description>
    </valueHelp>
    <valueHelp>
      <format>accept</format>
      <description>Accept if no prior rules are hit</description>
    </valueHelp>
    <constraint>
      <regex>(drop|accept)</regex>
    </constraint>
  </properties>
  <defaultValue>accept</defaultValue>
</leafNode>
<!-- include end -->
