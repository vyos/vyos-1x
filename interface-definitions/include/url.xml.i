<!-- include start from url.xml.i -->
<leafNode name="url">
  <properties>
    <help>Remote URL</help>
    <valueHelp>
      <format>url</format>
      <description>Remote URL</description>
    </valueHelp>
    <constraint>
      <regex>^https?:\/\/?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*(\:[0-9]+)*(\/.*)?</regex>
    </constraint>
    <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
