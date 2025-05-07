<!-- include start from serial/service/utils/sess-string-init.xml.i -->
<leafNode name="init-string">
  <properties>
    <help>Init Session String</help>
    <constraint>
      <regex>.{0,128}</regex>
    </constraint>
    <constraintErrorMessage>Session init string too long (limit 128 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
