<!-- include start from serial/service/utils/sess-string-term.xml.i -->
<leafNode name="terminate-string">
  <properties>
    <help>Session termination String</help>
    <constraint>
      <regex>.{0,127}</regex>
    </constraint>
    <constraintErrorMessage>Session termination string too long (limit 127 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
