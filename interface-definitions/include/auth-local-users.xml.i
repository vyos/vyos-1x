<!-- include start from auth-local-users.xml.i -->
<node name="local-users">
  <properties>
    <help>Local user authentication</help>
  </properties>
  <children>
    <tagNode name="username">
      <properties>
        <help>Username used for authentication</help>
        <valueHelp>
          <format>txt</format>
          <description>Username used for authentication</description>
        </valueHelp>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        <leafNode name="password">
          <properties>
            <help>Password used for authentication</help>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
