<!-- include start from generic-username.xml.i -->
<leafNode name="username">
  <properties>
    <help>Username used for authentication</help>
    <valueHelp>
      <format>txt</format>
      <description>Username</description>
    </valueHelp>
    <constraint>
      <regex>[[:ascii:]]{1,128}</regex>
    </constraint>
    <constraintErrorMessage>Username is limited to ASCII characters only, with a total length of 128</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
