<!-- included start from bgp/martian-next-hop.xml.i -->
<node name="martian">
  <properties>
    <help>Martian next-hops</help>
  </properties>
  <children>
    <leafNode name="next-hop">
      <properties>
        <help>Martian next-hop database</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<!-- included end -->
