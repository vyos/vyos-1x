<!-- include start from policy/action.xml.i -->
<leafNode name="action">
  <properties>
    <help>Action to take on entries matching this rule</help>
    <completionHelp>
      <list>permit deny</list>
    </completionHelp>
    <valueHelp>
      <format>permit</format>
      <description>Permit matching entries</description>
    </valueHelp>
    <valueHelp>
      <format>deny</format>
      <description>Deny matching entries</description>
    </valueHelp>
    <constraint>
      <regex>(permit|deny)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
