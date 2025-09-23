<!-- included start from bgp/reset-bgp-peer-group-vrf.xml.i -->
<tagNode name="peer-group">
  <properties>
    <help>Reset all members of peer-group</help>
    <completionHelp>
      <path>vrf name ${COMP_WORDS[4]} protocols bgp peer-group</path>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
  <children>
    #include <include/bgp/reset-bgp-neighbor-options.xml.i>
  </children>
</tagNode>
<!-- included end -->
