<!-- include start from accel-ppp/default-pool.xml.i -->
<leafNode name="default-pool">
  <properties>
    <help>Default client IP pool name</help>
    <valueHelp>
      <format>txt</format>
      <description>Default IP pool</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
