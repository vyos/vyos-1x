<!-- include start from url-http-https.xml.i -->
<leafNode name="url">
  <properties>
    <help>Remote URL</help>
    <valueHelp>
      <format>url</format>
      <description>Remote HTTP(S) URL</description>
    </valueHelp>
    <constraint>
      <validator name="url" argument="--scheme http --scheme https"/>
    </constraint>
    <constraintErrorMessage>Invalid HTTP(S) URL format</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
