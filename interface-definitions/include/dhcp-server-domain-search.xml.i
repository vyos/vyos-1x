<!-- included start from dhcp-server-domain-search.xml.i -->
<leafNode name="domain-search">
  <properties>
    <help>Client Domain Name search list</help>
    <constraint>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid domain name (RFC 1123 section 2).\nMay only contain letters, numbers and .-_</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<!-- included end -->
