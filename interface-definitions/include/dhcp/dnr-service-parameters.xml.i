<!-- include start from dhcp/dnr-service-parameters.xml.i -->
<node name="service-parameter">
  <properties>
    <help>DNR service parameter</help>
  </properties>
  <children>
    <leafNode name="alpn">
      <properties>
        <help>Application-Layer Protocol Negotiation (ALPN)</help>
        <completionHelp>
          <list>dot doq h2 h3</list>
        </completionHelp>
        <constraint>
          <regex>[A-Za-z0-9._-]+</regex>
        </constraint>
        <constraintErrorMessage>ALPN identifier may only contain letters, digits, dot, underscore, and hyphen</constraintErrorMessage>
        <multi/>
      </properties>
    </leafNode>
    #include <include/port-number.xml.i>
    <leafNode name="dohpath">
      <properties>
        <help>Relative DoH URI template path (plain paths auto-append {?dns}; custom templates must include {?dns})</help>
        <constraint>
          <regex>[[:graph:]]+</regex>
        </constraint>
        <constraintErrorMessage>DoH path must not contain whitespace</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
