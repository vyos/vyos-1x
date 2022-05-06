<!-- include start from monitoring/url.xml.i -->
<leafNode name="url">
  <properties>
    <help>Remote URL [REQUIRED]</help>
    <valueHelp>
      <format>url</format>
      <description>Remote URL</description>
    </valueHelp>
    <constraint>
      <regex>(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}?(\/.*)?</regex>
    </constraint>
    <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
