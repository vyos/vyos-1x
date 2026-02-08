<!-- include start from dhcp/dnr-common.xml.i -->
<leafNode name="priority">
  <properties>
    <help>DNR service priority</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Lower value means higher preference</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
    <constraintErrorMessage>DNR priority must be between 0 and 65535</constraintErrorMessage>
  </properties>
</leafNode>
<leafNode name="authentication-domain-name">
  <properties>
    <help>Authentication domain name (ADN) for encrypted DNS resolver</help>
    <constraint>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid authentication domain name</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
