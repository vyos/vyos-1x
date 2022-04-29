<!-- include start from firewall/action-accept-drop-reject.xml.i -->
<leafNode name="action">
  <properties>
    <help>Action for packets</help>
    <completionHelp>
      <list>accept drop reject</list>
    </completionHelp>
    <valueHelp>
      <format>accept</format>
      <description>Action to accept</description>
    </valueHelp>
    <valueHelp>
      <format>drop</format>
      <description>Action to drop</description>
    </valueHelp>
    <valueHelp>
      <format>reject</format>
      <description>Action to reject</description>
    </valueHelp>
    <constraint>
      <regex>(accept|drop|reject)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
