<!-- include start from monitoring/telegraf-output-tls.xml.i -->
<node name="tls">
  <properties>
    <help>Transport Layer Security (TLS) options</help>
  </properties>
  <children>
    #include <include/pki/ca-certificate.xml.i>
    <leafNode name="ca-certificate">
      <properties>
        <help>Certificate Authority to verify the remote server certificate</help>
      </properties>
    </leafNode>
    #include <include/pki/certificate.xml.i>
    <leafNode name="certificate">
      <properties>
        <help>Client certificate presented to the remote server (mutual TLS)</help>
      </properties>
    </leafNode>
    <leafNode name="server-name">
      <properties>
        <help>Server name for SNI and remote certificate verification</help>
        <valueHelp>
          <format>txt</format>
          <description>Fully qualified domain name</description>
        </valueHelp>
        <constraint>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="no-verify">
      <properties>
        <help>Do not verify the remote server certificate (insecure)</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
