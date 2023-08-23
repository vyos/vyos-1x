<!-- include start from interface/macsec-key.xml.i -->
<leafNode name="key">
  <properties>
    <help>MACsec static key</help>
    <valueHelp>
      <format>txt</format>
      <description>16-byte (128-bit) hex-string (32 hex-digits) for gcm-aes-128 or 32-byte (256-bit) hex-string (64 hex-digits) for gcm-aes-256</description>
    </valueHelp>
    <constraint>
      <regex>[A-Fa-f0-9]{32}</regex>
      <regex>[A-Fa-f0-9]{64}</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
