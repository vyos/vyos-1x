<!-- include start from certificate-key.xml.i -->
<leafNode name="key-file">
  <properties>
    <help>Certificate private key in x509 PEM format</help>
    <valueHelp>
      <format>filename</format>
      <description>File in /config/auth directory</description>
    </valueHelp>
    <constraint>
      <validator name="file-path" argument="--strict --parent-dir /config/auth"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
