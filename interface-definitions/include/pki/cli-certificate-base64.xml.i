<!-- include start from pki/cli-certificate-base64.xml.i -->
<leafNode name="certificate">
  <properties>
    <help>Certificate in PEM format</help>
    <constraint>
      <validator name="base64"/>
    </constraint>
    <constraintErrorMessage>Certificate is not base64-encoded</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
