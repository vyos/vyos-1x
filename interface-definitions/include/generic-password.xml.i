<!-- include start from generic-password.xml.i -->
<leafNode name="password">
  <properties>
    <help>Password used for authentication</help>
    <valueHelp>
      <format>txt</format>
      <description>Password</description>
    </valueHelp>
    <constraint>
      <regex>[[:ascii:]]{1,128}</regex>
    </constraint>
    <constraintErrorMessage>Password is limited to ASCII characters only, with a total length of 128</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
