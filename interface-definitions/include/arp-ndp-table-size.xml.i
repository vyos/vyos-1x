<!-- include start from arp-ndp-table-size.xml.i -->
<leafNode name="table-size">
  <properties>
    <help>Maximum number of entries to keep in the cache</help>
    <completionHelp>
      <list>1024 2048 4096 8192 16384 32768</list>
    </completionHelp>
    <constraint>
      <regex>(1024|2048|4096|8192|16384|32768)</regex>
    </constraint>
  </properties>
  <defaultValue>8192</defaultValue>
</leafNode>
<!-- include end -->
