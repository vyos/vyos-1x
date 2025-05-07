<!-- include start from serial/service/utils/sess-string-term.xml.i -->
<leafNode name="term-string">
  <properties>
    <help>Terminate Session String</help>
    <constraint>
      <regex>.{0,128}</regex>
    </constraint>
    <constraintErrorMessage>Session termination tring too long (limit 128 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
