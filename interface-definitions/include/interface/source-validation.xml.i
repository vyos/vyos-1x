<!-- include start from interface/source-validation.xml.i -->
<leafNode name="source-validation">
  <properties>
    <help>Source validation by reversed path (RFC3704)</help>
    <completionHelp>
      <list>strict loose disable</list>
    </completionHelp>
    <valueHelp>
      <format>strict</format>
      <description>Enable Strict Reverse Path Forwarding as defined in RFC3704</description>
    </valueHelp>
    <valueHelp>
      <format>loose</format>
      <description>Enable Loose Reverse Path Forwarding as defined in RFC3704</description>
    </valueHelp>
    <valueHelp>
      <format>disable</format>
      <description>No source validation</description>
    </valueHelp>
    <constraint>
      <regex>(strict|loose|disable)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
