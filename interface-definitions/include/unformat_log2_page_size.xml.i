<!-- include start from unformat_log2_page_size.xml.i -->
<completionHelp>
  <list>default default-hugepage</list>
  <script>sudo ${vyos_completion_dir}/list_mem_page_size.py</script>
</completionHelp>
<valueHelp>
  <format>default</format>
  <description>Default</description>
</valueHelp>
<valueHelp>
  <format>default-hugepage</format>
  <description>Default huge-page</description>
</valueHelp>
<constraint>
  <regex>(default|default-hugepage|4K|8K|1024K|64K|256K|2048K|4096K|16384K|262144K|1048576K|16777216K|1M|2M|4M|16M|256M|1024M|16384M|1G|16G)</regex>
</constraint>
<!-- include end -->
