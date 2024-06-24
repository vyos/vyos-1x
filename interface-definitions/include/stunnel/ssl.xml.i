<!-- include start from stunnel/ssl.xml.i -->
<node name="ssl">
  <properties>
    <help>SSL Certificate, SSL Key and CA</help>
  </properties>
  <children>
    #include <include/pki/ca-certificate-multi.xml.i>
    #include <include/pki/certificate.xml.i>
  </children>
</node>
<!-- include end -->
