<!-- include start from ipsec/authentication-x509.xml.i -->
<node name="x509">
  <properties>
    <help>X.509 certificate</help>
  </properties>
  <children>
    #include <include/pki/certificate-key.xml.i>
    #include <include/pki/ca-certificate-multi.xml.i>
  </children>
</node>
<!-- include end -->
