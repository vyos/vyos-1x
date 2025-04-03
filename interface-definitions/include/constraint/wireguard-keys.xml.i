<!-- include start from constraint/wireguard-keys.xml.i -->
<constraint>
  <validator name="base64" argument="--decoded-len 32"/>
</constraint>
<constraintErrorMessage>Key must be Base64-encoded with 32 bytes in length</constraintErrorMessage>
<!-- include end -->
