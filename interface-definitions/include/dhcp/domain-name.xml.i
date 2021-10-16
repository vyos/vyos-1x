<!-- include start from dhcp/domain-name.xml.i -->
<leafNode name="domain-name">
  <properties>
    <help>Client Domain Name</help>
    <constraint>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid domain name (RFC 1123 section 2).\nMay only contain letters, numbers and .-_</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
