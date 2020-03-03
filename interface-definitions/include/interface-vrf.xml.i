<leafNode name="vrf">
  <properties>
    <help>VRF instance name</help>
    <completionHelp>
      <path>vrf name</path>
    </completionHelp>
    <constraint>
      <validator name="interface-name"/>
    </constraint>
    <constraintErrorMessage>VRF name not allowed or to long</constraintErrorMessage>
  </properties>
</leafNode>
