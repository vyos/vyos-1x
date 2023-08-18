<!-- include start from sssd-domain.xml.i -->
<node name="sssd">
  <properties>
    <help>SSSD based authentication</help>
  </properties>
  <children>
    <tagNode name="ipa-domain">
      <properties>
        <help>SSSD IPA domain</help>
        <valueHelp>
          <format>txt</format>
          <description>IPA domain name</description>
        </valueHelp>
        <constraint>
          <validator name="fqdn" />
        </constraint>
      </properties>
      <children>
       #include <include/generic-disable-node.xml.i>
        <leafNode name="cache-credentials">
          <properties>
            <help>Cache sssd credentials for offline use</help>
            <valueless />
          </properties>
        </leafNode>
        <leafNode name="krb5-store-password-if-offline">
          <properties>
            <help>Cache krb5 credentials if offline</help>
            <valueless />
          </properties>
        </leafNode>
        <leafNode name="ipa-hostname">
          <properties>
            <help>Specify the hostname of the IPA client</help>
            <valueHelp>
              <format>txt</format>
              <description>FQDN of the IPA client</description>
            </valueHelp>
            <constraint>
              <validator name="fqdn" />
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="ipa-server">
          <properties>
            <help>Specify an IPA server</help>
            <valueHelp>
              <format>txt</format>
              <description>FQDN of an IPA server</description>
            </valueHelp>
            <constraint>
              <validator name="fqdn" />
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="krb-realm">
          <properties>
            <help>Specify the Kerberos realm</help>
            <valueHelp>
              <format>txt</format>
              <description>A kerberos Realm</description>
            </valueHelp>
            <constraint>
              <validator name="fqdn" />
            </constraint>
          </properties>
        </leafNode>
        #include <include/pki/ca-certificate.xml.i>
        #include <include/kerberos/keytab.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
