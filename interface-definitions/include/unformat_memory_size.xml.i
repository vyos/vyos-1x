<!-- include start from unformat_memory_size.xml.i -->
<valueHelp>
  <format>&lt;number&gt;</format>
  <description>byte</description>
</valueHelp>
<valueHelp>
  <format>&lt;number&gt;K</format>
  <description>Kilobyte</description>
</valueHelp>
<valueHelp>
  <format>&lt;number&gt;M</format>
  <description>Megabyte</description>
</valueHelp>
<valueHelp>
  <format>&lt;number&gt;G</format>
  <description>Gigabyte</description>
</valueHelp>
<constraint>
  <validator name="numeric" argument="--range 0-4294967295"/>
  <regex>(\d+|\d+K|\d+M|\d+G)</regex>
</constraint>
<!-- include end -->
