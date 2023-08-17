<!-- include start from radius-server-key.xml.i -->
<leafNode name="key">
  <properties>
    <help>Shared secret key</help>
    <valueHelp>
      <format>txt</format>
      <description>Password string (key)</description>
    </valueHelp>
    <constraint>
      <regex>[[:ascii:]]{1,128}</regex>
    </constraint>
    <constraintErrorMessage>Password must be less then 128 characters</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
