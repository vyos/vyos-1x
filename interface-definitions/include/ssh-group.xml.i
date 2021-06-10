<!-- include start from ssh-group.xml.i -->
<leafNode name="group">
  <properties>
    <help>Allow members of a group to login</help>
    <constraint>
      <regex>[a-z_][a-z0-9_-]{1,31}[$]?</regex>
    </constraint>
    <constraintErrorMessage>illegal characters or more than 32 characters</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
