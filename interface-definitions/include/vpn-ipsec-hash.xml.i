<!-- include start from vpn-ipsec-hash.xml.i -->
<leafNode name="hash">
  <properties>
    <help>Hash algorithm</help>
    <completionHelp>
      <list>md5 md5_128 sha1 sha1_160 sha256 sha256_96 sha384 sha512 aesxcbc aescmac aes128gmac aes192gmac aes256gmac</list>
    </completionHelp>
    <valueHelp>
      <format>md5</format>
      <description>MD5 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>md5_128</format>
      <description>MD5_128 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha1</format>
      <description>SHA1 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha1_160</format>
      <description>SHA1_160 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha256</format>
      <description>SHA2_256_128 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha256_96</format>
      <description>SHA2_256_96 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha384</format>
      <description>SHA2_384_192 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>sha512</format>
      <description>SHA2_512_256 HMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aesxcbc</format>
      <description>AES XCBC</description>
    </valueHelp>
    <valueHelp>
      <format>aescmac</format>
      <description>AES CMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aes128gmac</format>
      <description>128-bit AES-GMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aes192gmac</format>
      <description>192-bit AES-GMAC</description>
    </valueHelp>
    <valueHelp>
      <format>aes256gmac</format>
      <description>256-bit AES-GMAC</description>
    </valueHelp>
    <constraint>
      <regex>(md5|md5_128|sha1|sha1_160|sha256|sha256_96|sha384|sha512|aesxcbc|aescmac|aes128gmac|aes192gmac|aes256gmac)</regex>
    </constraint>
  </properties>
  <defaultValue>sha1</defaultValue>
</leafNode>
<!-- include end -->
