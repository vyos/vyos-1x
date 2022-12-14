<!-- include start from certificate.xml.i -->
<leafNode name="cert-file">
  <properties>
    <help>Certificate public key in x509 PEM format</help>
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
