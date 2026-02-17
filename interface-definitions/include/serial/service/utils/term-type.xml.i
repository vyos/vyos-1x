<!-- include start from serial/service/utils/term-type.xml.i -->
<leafNode name="terminal-type">
  <properties>
    <help>Specifies the type of terminal connected</help>
    <constraint>
      <regex>.{0,17}</regex>
    </constraint>
    <constraintErrorMessage>Terminal type string too long (limit 17 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
