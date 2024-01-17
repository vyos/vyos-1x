<!-- include start from accel-ppp/default-pool.xml.i -->
<leafNode name="default-ipv6-pool">
  <properties>
    <help>Default client IPv6 pool name</help>
    <completionHelp>
      <path>${COMP_WORDS[@]:1:${#COMP_WORDS[@]}-3} client-ipv6-pool</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Default IPv6 pool</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
