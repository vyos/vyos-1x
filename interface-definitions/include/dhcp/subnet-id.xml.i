<!-- include start from dhcp/subnet-id.xml.i -->
<leafNode name="subnet-id">
    <properties>
    <help>Unique ID mapped to leases in the lease file</help>
    <valueHelp>
        <format>u32:1-4294967294</format>
        <description>Unique subnet ID</description>
    </valueHelp>
    <constraint>
        <validator name="numeric" argument="--range 1-4294967294"/>
    </constraint>
    </properties>
</leafNode>
<!-- include end -->
