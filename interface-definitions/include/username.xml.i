<!-- include start from username.xml.i -->
<leafNode name="username">
  <properties>
    <help>Authentication username</help>
    <constraint>
      <regex>^[-_a-zA-Z0-9.]{1,100}</regex>
    </constraint>
    <constraintErrorMessage>Illegal characters or more than 100 characters</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
