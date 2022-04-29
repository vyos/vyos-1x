<!-- include start from vpn-ipsec-encryption.xml.i -->
<leafNode name="encryption">
  <properties>
    <help>Encryption algorithm</help>
    <completionHelp>
      <list>null aes128 aes192 aes256 aes128ctr aes192ctr aes256ctr aes128ccm64 aes192ccm64 aes256ccm64 aes128ccm96 aes192ccm96 aes256ccm96 aes128ccm128 aes192ccm128 aes256ccm128 aes128gcm64 aes192gcm64 aes256gcm64 aes128gcm96 aes192gcm96 aes256gcm96 aes128gcm128 aes192gcm128 aes256gcm128 aes128gmac aes192gmac aes256gmac 3des blowfish128 blowfish192 blowfish256 camellia128 camellia192 camellia256 camellia128ctr camellia192ctr camellia256ctr camellia128ccm64 camellia192ccm64 camellia256ccm64 camellia128ccm96 camellia192ccm96 camellia256ccm96 camellia128ccm128 camellia192ccm128 camellia256ccm128 serpent128 serpent192 serpent256 twofish128 twofish192 twofish256 cast128 chacha20poly1305</list>
    </completionHelp>
    <valueHelp>
      <format>null</format>
      <description>Null encryption</description>
    </valueHelp>
    <valueHelp>
      <format>aes128</format>
      <description>128 bit AES-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>aes192</format>
      <description>192 bit AES-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>aes256</format>
      <description>256 bit AES-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>aes128ctr</format>
      <description>128 bit AES-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>aes192ctr</format>
      <description>192 bit AES-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>aes256ctr</format>
      <description>256 bit AES-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>aes128ccm64</format>
      <description>128 bit AES-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192ccm64</format>
      <description>192 bit AES-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes256ccm64</format>
      <description>256 bit AES-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128ccm96</format>
      <description>128 bit AES-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192ccm96</format>
      <description>192 bit AES-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes256ccm96</format>
      <description>256 bit AES-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128ccm128</format>
      <description>128 bit AES-CCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192ccm128</format>
      <description>192 bit AES-CCM with 128 bit IC</description>
    </valueHelp>
    <valueHelp>
      <format>aes256ccm128</format>
      <description>256 bit AES-CCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128gcm64</format>
      <description>128 bit AES-GCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192gcm64</format>
      <description>192 bit AES-GCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes256gcm64</format>
      <description>256 bit AES-GCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128gcm96</format>
      <description>128 bit AES-GCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192gcm96</format>
      <description>192 bit AES-GCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes256gcm96</format>
      <description>256 bit AES-GCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128gcm128</format>
      <description>128 bit AES-GCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes192gcm128</format>
      <description>192 bit AES-GCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes256gcm128</format>
      <description>256 bit AES-GCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>aes128gmac</format>
      <description>Null encryption with 128 bit AES-GMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aes192gmac</format>
      <description>Null encryption with 192 bit AES-GMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aes256gmac</format>
      <description>Null encryption with 256 bit AES-GMAC</description>
    </valueHelp>
    <valueHelp>
      <format>3des</format>
      <description>168 bit 3DES-EDE-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>blowfish128</format>
      <description>128 bit Blowfish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>blowfish192</format>
      <description>192 bit Blowfish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>blowfish256</format>
      <description>256 bit Blowfish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>camellia128</format>
      <description>128 bit Camellia-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>camellia192</format>
      <description>192 bit Camellia-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>camellia256</format>
      <description>256 bit Camellia-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>camellia128ctr</format>
      <description>128 bit Camellia-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>camellia192ctr</format>
      <description>192 bit Camellia-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>camellia256ctr</format>
      <description>256 bit Camellia-COUNTER</description>
    </valueHelp>
    <valueHelp>
      <format>camellia128ccm64</format>
      <description>128 bit Camellia-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia192ccm64</format>
      <description>192 bit Camellia-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia256ccm64</format>
      <description>256 bit Camellia-CCM with 64 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia128ccm96</format>
      <description>128 bit Camellia-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia192ccm96</format>
      <description>192 bit Camellia-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia256ccm96</format>
      <description>256 bit Camellia-CCM with 96 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia128ccm128</format>
      <description>128 bit Camellia-CCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia192ccm128</format>
      <description>192 bit Camellia-CCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>camellia256ccm128</format>
      <description>256 bit Camellia-CCM with 128 bit ICV</description>
    </valueHelp>
    <valueHelp>
      <format>serpent128</format>
      <description>128 bit Serpent-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>serpent192</format>
      <description>192 bit Serpent-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>serpent256</format>
      <description>256 bit Serpent-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>twofish128</format>
      <description>128 bit Twofish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>twofish192</format>
      <description>192 bit Twofish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>twofish256</format>
      <description>256 bit Twofish-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>cast128</format>
      <description>128 bit CAST-CBC</description>
    </valueHelp>
    <valueHelp>
      <format>chacha20poly1305</format>
      <description>256 bit ChaCha20/Poly1305 with 128 bit ICV</description>
    </valueHelp>
    <constraint>
      <regex>(null|aes128|aes192|aes256|aes128ctr|aes192ctr|aes256ctr|aes128ccm64|aes192ccm64|aes256ccm64|aes128ccm96|aes192ccm96|aes256ccm96|aes128ccm128|aes192ccm128|aes256ccm128|aes128gcm64|aes192gcm64|aes256gcm64|aes128gcm96|aes192gcm96|aes256gcm96|aes128gcm128|aes192gcm128|aes256gcm128|aes128gmac|aes192gmac|aes256gmac|3des|blowfish128|blowfish192|blowfish256|camellia128|camellia192|camellia256|camellia128ctr|camellia192ctr|camellia256ctr|camellia128ccm64|camellia192ccm64|camellia256ccm64|camellia128ccm96|camellia192ccm96|camellia256ccm96|camellia128ccm128|camellia192ccm128|camellia256ccm128|serpent128|serpent192|serpent256|twofish128|twofish192|twofish256|cast128|chacha20poly1305)</regex>
    </constraint>
  </properties>
  <defaultValue>aes128</defaultValue>
</leafNode>
<!-- include end -->
