<!-- include start from firewall/action.xml.i -->
<leafNode name="action">
  <properties>
    <help>Rule action [REQUIRED]</help>
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
      <regex>^(permit|deny)$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
