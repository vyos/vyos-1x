<!-- include start from serial/service/utils/sess-string-init.xml.i -->
<leafNode name="init-string">
  <properties>
    <help>Init Session String</help>
    <constraint>
      <regex>.{0,127}</regex>
    </constraint>
    <constraintErrorMessage>Session init string too long (limit 127 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
