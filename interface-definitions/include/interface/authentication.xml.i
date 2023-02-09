<!-- include start from interface/authentication.xml.i -->
<node name="authentication">
  <properties>
    <help>Authentication settings</help>
  </properties>
  <children>
    <leafNode name="user">
      <properties>
        <help>User name</help>
        <valueHelp>
          <format>txt</format>
          <description>Username used for connection</description>
        </valueHelp>
        <constraint>
          <regex>[[:alnum:]][-_#@[:alnum:]]{0,127}</regex>
        </constraint>
        <constraintErrorMessage>Username is limited to alphanumerical characters, -, _, #, and @ with a total lenght of 128</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="password">
      <properties>
        <help>Password</help>
        <valueHelp>
          <format>txt</format>
          <description>Password used for connection</description>
        </valueHelp>
        <constraint>
          <regex>[[:ascii:]]{1,128}</regex>
        </constraint>
        <constraintErrorMessage>Password is limited to ASCII characters only, with a total lenght of 128</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
