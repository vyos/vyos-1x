<!-- include start from webproxy-url-filtering.xml.i -->
<leafNode name="allow-category">
  <properties>
    <help>Category to allow</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_webproxy_category.sh</script>
    </completionHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="allow-ipaddr-url">
  <properties>
    <help>Allow IP address URLs</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="block-category">
  <properties>
    <help>Category to block</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_webproxy_category.sh</script>
    </completionHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="default-action">
  <properties>
    <help>Default action (default: allow)</help>
    <completionHelp>
      <list>allow block</list>
    </completionHelp>
    <valueHelp>
      <format>allow</format>
      <description>Default filter action is allow)</description>
    </valueHelp>
    <valueHelp>
      <format>block</format>
      <description>Default filter action is block</description>
    </valueHelp>
    <constraint>
      <regex>(allow|block)</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="enable-safe-search">
  <properties>
    <help>Enable safe-mode search on popular search engines</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="local-block-keyword">
  <properties>
    <help>Local keyword to block</help>
    <valueHelp>
      <format>keyword</format>
      <description>Keyword (or regex) to block</description>
    </valueHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="local-block-url">
  <properties>
    <help>Local URL to block</help>
    <valueHelp>
      <format>url</format>
      <description>Local URL to block (without "http://")</description>
    </valueHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="local-block">
  <properties>
    <help>Local site to block</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IP address of site to block</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="fqdn"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<leafNode name="local-ok-url">
  <properties>
    <help>Local URL to allow</help>
    <valueHelp>
      <format>url</format>
      <description>Local URL to allow (without "http://")</description>
    </valueHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="local-ok">
  <properties>
    <help>Local site to allow</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IP address of site to allow</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="fqdn"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<leafNode name="log">
  <properties>
    <help>Log block category</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_webproxy_category.sh</script>
      <list>all</list>
    </completionHelp>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
