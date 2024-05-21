<!-- include start from haproxy/http-response-headers.xml.i -->
<tagNode name="http-response-headers">
  <properties>
    <help>Headers to include in HTTP response</help>
    <valueHelp>
      <format>txt</format>
      <description>HTTP header name</description>
    </valueHelp>
    <constraint>
      <regex>[-a-zA-Z]+</regex>
    </constraint>
    <constraintErrorMessage>Header names must only include alphabetical characters and hyphens</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="value">
      <properties>
        <help>HTTP header value</help>
        <valueHelp>
          <format>txt</format>
          <description>HTTP header value</description>
        </valueHelp>
        <constraint>
          <regex>[[:ascii:]]{1,256}</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
