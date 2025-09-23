<!-- included start from bgp/reset-bgp-neighbor-options.xml.i -->
<node name="in">
  <properties>
    <help>Send route-refresh unless using 'soft-reconfiguration inbound'</help>
  </properties>
  <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
  <children>
    <leafNode name="prefix-filter">
      <properties>
        <help>Push out prefix-list ORF and do inbound soft reconfig</help>
      </properties>
      <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
    </leafNode>
  </children>
</node>
<leafNode name="message-stats">
  <properties>
    <help>Reset message statistics</help>
  </properties>
  <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
</leafNode>
<leafNode name="out">
  <properties>
    <help>Resend all outbound updates</help>
  </properties>
  <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
</leafNode>
<node name="soft">
  <properties>
    <help>Soft reconfig inbound and outbound updates</help>
  </properties>
  <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
  <children>
    <node name="in">
      <properties>
        <help>Send route-refresh unless using 'soft-reconfiguration inbound'</help>
      </properties>
      <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
    </node>
    <node name="out">
      <properties>
        <help>Resend all outbound updates</help>
      </properties>
      <command>${vyos_op_scripts_dir}/bgp.py reset --command="$*"</command>
    </node>
  </children>
</node>
<!-- included end -->
