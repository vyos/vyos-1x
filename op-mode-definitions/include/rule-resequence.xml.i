<!-- included start from show-nht.xml.i -->
<node name="rule-resequence">
  <properties>
    <help>Resequence rules</help>
  </properties>
  <command>${vyos_op_scripts_dir}/generate_service_rule-resequence.py --service $2</command>
  <children>
    <tagNode name="start">
      <properties>
        <help>Set the first sequence number</help>
        <completionHelp>
          <list>1-1000</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/generate_service_rule-resequence.py --service $2 --start $5</command>
      <children>
        <tagNode name="step">
          <properties>
            <help>Step between rules</help>
            <completionHelp>
              <list>1-1000</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/generate_service_rule-resequence.py --service $2 --start $5 --step $7</command>
        </tagNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- included end -->
