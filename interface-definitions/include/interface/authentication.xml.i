<!-- include start from interface/authentication.xml.i -->
<node name="authentication">
  <properties>
    <help>Authentication settings</help>
  </properties>
  <children>
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
  </children>
</node>
<!-- include end -->
