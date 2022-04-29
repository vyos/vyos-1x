<!-- include start from ssh-user.xml.i -->
<leafNode name="user">
  <properties>
    <help>Allow specific users to login</help>
    <constraint>
      <regex>[-_a-zA-Z0-9.]{1,100}</regex>
    </constraint>
    <constraintErrorMessage>Illegal characters or more than 100 characters</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
