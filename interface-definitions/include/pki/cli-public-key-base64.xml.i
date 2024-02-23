<!-- include start from pki/cli-public-key-base64.xml.i -->
<leafNode name="key">
  <properties>
    <help>Public key in PEM format</help>
    <constraint>
      <validator name="base64"/>
    </constraint>
    <constraintErrorMessage>Public key is not base64-encoded</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
