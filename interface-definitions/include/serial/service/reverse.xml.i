<!-- include start from serial/service/reverse.xml.i -->
<node name="reverse">
  <properties>
    <help>Reverse connection profile</help>
  </properties>
  <children>
    <leafNode name="auth-user">
      <properties>
        <help>Enable authenticate user</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/serial/service/utils/ip-aliasing.xml.i>
    #include <include/serial/service/utils/multisession.xml.i>
    <leafNode name="allow-multiple-connection">
      <properties>
        <help>Enable allow multiple connections</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
