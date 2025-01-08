<!-- include start from auth-psk-secret.xml.i -->
<leafNode name="secret">
  <properties>
    <help>pre-shared secret key</help>
    <valueHelp>
      <format>txt</format>
      <description>16byte pre-shared-secret key (32 character hexadecimal key)</description>
    </valueHelp>
    <constraint>
      <validator name="psk-secret"/>
    </constraint>
    <constraintErrorMessage>Pre-Shared-Keys must be at leas 16 bytes long, which implies at least 32 characterss</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
