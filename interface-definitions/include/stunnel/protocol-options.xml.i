<!-- include start from stunel/protocol-options.xml.i -->
<node name="options">
  <properties>
    <help>Advanced protocol options</help>
  </properties>
  <children>
    <leafNode name="authentication">
      <properties>
        <help>Authentication type for the protocol negotiations</help>
          <completionHelp>
            <list>basic ntlm plain login</list>
          </completionHelp>
          <valueHelp>
            <format>basic</format>
            <description>The default 'connect' authentication type</description>
          </valueHelp>
          <valueHelp>
            <format>ntlm</format>
            <description>Supported authentication types for the 'connect' protocol</description>
          </valueHelp>
          <valueHelp>
            <format>plain</format>
            <description>The default 'smtp' authentication type</description>
          </valueHelp>
          <valueHelp>
            <format>login</format>
            <description>Supported authentication types for the 'smtp' protocol</description>
          </valueHelp>
          <constraint>
            <regex>(basic|ntlm|plain|login)</regex>
          </constraint>
      </properties>
    </leafNode>
    <leafNode name="domain">
      <properties>
        <help>Domain for the 'connect' protocol.</help>
        <valueHelp>
          <format>domain</format>
          <description>domain</description>
        </valueHelp>
        <constraint>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="host">
      <properties>
        <help>Destination address for the 'connect' protocol</help>
      </properties>
      <children>
        #include <include/stunnel/address.xml.i>
        #include <include/port-number.xml.i>
      </children>
    </node>
    <leafNode name="password">
      <properties>
        <help>Password for the protocol negotiations</help>
        <valueHelp>
          <format>txt</format>
          <description>Authentication password</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="username">
      <properties>
        <help>Username for the protocol negotiations</help>
        <valueHelp>
          <format>txt</format>
          <description>Authentication username</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
