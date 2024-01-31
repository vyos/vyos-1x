<!-- include start from haproxy/rule.xml.i -->
<tagNode name="rule">
  <properties>
    <help>Proxy rule number</help>
    <valueHelp>
      <format>u32:1-10000</format>
      <description>Number for this proxy rule</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-10000"/>
    </constraint>
    <constraintErrorMessage>Proxy rule number must be between 1 and 10000</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="domain-name">
      <properties>
        <help>Domain name to match</help>
        <valueHelp>
          <format>txt</format>
          <description>Domain address to match</description>
        </valueHelp>
        <constraint>
          <validator name="fqdn"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <node name="set">
      <properties>
        <help>Proxy modifications</help>
      </properties>
      <children>
        <leafNode name="redirect-location">
          <properties>
            <help>Set URL location</help>
            <valueHelp>
              <format>url</format>
              <description>Set URL location</description>
            </valueHelp>
            <constraint>
              <regex>^\/[\w\-.\/]+$</regex>
            </constraint>
            <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="server">
          <properties>
            <help>Server name</help>
            <constraint>
              <regex>[-_a-zA-Z0-9]+</regex>
            </constraint>
            <constraintErrorMessage>Server name must be alphanumeric and can contain hyphen and underscores</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="ssl">
      <properties>
        <help>SSL match options</help>
        <completionHelp>
          <list>req-ssl-sni ssl-fc-sni</list>
        </completionHelp>
        <valueHelp>
          <format>req-ssl-sni</format>
          <description>SSL Server Name Indication (SNI) request match</description>
        </valueHelp>
        <valueHelp>
          <format>ssl-fc-sni</format>
          <description>SSL frontend connection Server Name Indication match</description>
        </valueHelp>
        <valueHelp>
          <format>ssl-fc-sni-end</format>
          <description>SSL frontend match end of connection Server Name Indication</description>
        </valueHelp>
        <constraint>
          <regex>(req-ssl-sni|ssl-fc-sni|ssl-fc-sni-end)</regex>
        </constraint>
      </properties>
    </leafNode>
    <node name="url-path">
      <properties>
        <help>URL path match</help>
      </properties>
      <children>
        <leafNode name="begin">
          <properties>
            <help>Begin URL match</help>
            <valueHelp>
              <format>url</format>
              <description>Begin URL</description>
            </valueHelp>
            <constraint>
              <regex>^\/[\w\-.\/]+$</regex>
            </constraint>
            <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
            <multi/>
          </properties>
        </leafNode>
        <leafNode name="end">
          <properties>
            <help>End URL match</help>
            <valueHelp>
              <format>url</format>
              <description>End URL</description>
            </valueHelp>
            <constraint>
              <regex>^\/[\w\-.\/]+$</regex>
            </constraint>
            <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
            <multi/>
          </properties>
        </leafNode>
        <leafNode name="exact">
          <properties>
            <help>Exactly URL match</help>
            <valueHelp>
              <format>url</format>
              <description>Exactly URL</description>
            </valueHelp>
            <constraint>
              <regex>^\/[\w\-.\/]*$</regex>
            </constraint>
            <constraintErrorMessage>Incorrect URL format</constraintErrorMessage>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</tagNode>
<!-- include end -->
