<!-- include start from firewall/state.xml.i -->
<leafNode name="state">
  <properties>
    <help>Session state</help>
    <completionHelp>
      <list>established invalid new related</list>
    </completionHelp>
    <valueHelp>
      <format>established</format>
      <description>Established state</description>
    </valueHelp>
    <valueHelp>
      <format>invalid</format>
      <description>Invalid state</description>
    </valueHelp>
    <valueHelp>
      <format>new</format>
      <description>New state</description>
    </valueHelp>
    <valueHelp>
      <format>related</format>
      <description>Related state</description>
    </valueHelp>
    <constraint>
      <regex>(established|invalid|new|related)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
