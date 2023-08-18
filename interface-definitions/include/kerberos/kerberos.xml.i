<!-- include start from kerberos.xml.i -->
<node name="kerberos">
  <properties>
    <help>Global kerberos settings</help>
  </properties>
  <children>
    <leafNode name="dns-lookup-realm">
      <properties>
        <help>Use the DNS realm discovery mechanism</help>
        <valueless />
      </properties>
    </leafNode>
    <leafNode name="dns-lookup-kdc">
      <properties>
        <help>Use the DNS KDC discovery mechanism</help>
        <valueless />
      </properties>
    </leafNode>
    <leafNode name="rdns">
      <properties>
        <help>Use rDNS</help>
        <valueless />
      </properties>
    </leafNode>
    <leafNode name="ticket-lifetime">
      <properties>
        <help>Ticket lifetime in seconds</help>
        <valueHelp>
          <format>u32</format>
          <description>Ticket lifetime in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295" />
        </constraint>
        <constraintErrorMessage>Ticket lifetime must be between 0 and 4294967295 (49 days)</constraintErrorMessage>
      </properties>
      <defaultValue>86400</defaultValue>
    </leafNode>
    <leafNode name="forwardable">
      <properties>
        <help>Ticket should be forwardable</help>
        <valueless />
      </properties>
    </leafNode>
    <leafNode name="default-realm">
      <properties>
        <help>Default realm</help>
        <completionHelp>
          <path>Default realm</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="default-keytab">
      <properties>
        <help>Default keytab</help>
        <completionHelp>
          <path>system login kerberos keytab principal</path>
        </completionHelp>
        <constraint>
          <validator name="krb-principal-name" />
        </constraint>
      </properties>
    </leafNode>
    <node name="keytab">
      <properties>
        <help>Kerberos keytabs</help>
      </properties>
      <children>
        <tagNode name="principal">
          <properties>
            <help>Kerberos principal</help>
            <valueHelp>
              <format>txt</format>
              <description>Principal name</description>
            </valueHelp>
            <constraint>
              <validator name="krb-principal-name" />
            </constraint>
            <constraintErrorMessage>Must be a valid principal name.</constraintErrorMessage>
          </properties>
          <children>
            <leafNode name="krb-keytab">
              <properties>
                <help>BASE64 Keytab</help>
                <valueHelp>
                  <format>txt</format>
                  <description>BASE64 Keytab</description>
                </valueHelp>
                <constraint>
                  <validator name="base64" />
                </constraint>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
