<!-- include start from serial/service/utils/tls-port.xml.i -->
<node name="tls">
  <properties>
    <help>TLS setting</help>
  </properties>
  <children>
    #include <include/serial/service/utils/tls-common.xml.i>
    #include <include/serial/service/utils/tls-use-global.xml.i>
  </children>
</node>
<!-- include end -->
