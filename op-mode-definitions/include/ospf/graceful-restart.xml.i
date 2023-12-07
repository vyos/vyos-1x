<node name="graceful-restart">
    <properties>
      <help>Show OSPF Graceful Restart</help>
    </properties>
    <children>
      <leafNode name="helper">
        <properties>
          <help>OSPF Graceful Restart helper details</help>
        </properties>
        <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      </leafNode>
    </children>
  </node>
