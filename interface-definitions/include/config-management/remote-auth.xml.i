<!-- include start from config-management/remote-auth.xml.i -->
<node name="authentication">
  <properties>
    <help>Authentication settings for remote server</help>
  </properties>
  <children>
    #include <include/generic-username.xml.i>
    #include <include/generic-password.xml.i>
  </children>
</node>
#include <include/config-management/remote.xml.i>
<!-- include end -->
