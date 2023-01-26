<!-- include start from openconnect-config-per-x.xml.i -->
<node name="config-per-x">
    <properties>
        <help>Configures ocserv to search the configured directory for a config file matching the Group name or username</help>
    </properties>
    <children>
        <leafNode name="mode">
            <properties>
                <help>ocserv will ignore these configs if groupconfig is enabled TODO: explain this in better detail - need to make it clear this is in reference to the groupconfig vyos config that lives up one level from here</help>
                <valueHelp>
                    <format>user</format>
                    <description>ocserv config file loaded by matching file in configured directory to the users username</description>
                </valueHelp>
                <valueHelp>
                    <format>group</format>
                    <description>ocserv config file loaded by matching RADIUS class attribute in the RADIUS server response to a file in the configured directory</description>
                </valueHelp>
                <constraint>
                    <regex>(user|group)</regex>
                </constraint>
                <constraintErrorMessage>Invalid config-per-x. Must be one of: user,  group </constraintErrorMessage>
                <completionHelp>
                    <list>user group</list>
                </completionHelp>
            </properties>
        </leafNode>
        <leafNode name="directory">
            <properties>
                <help>Child directory of /config/auth e.g. /config/auth/ocserv/config-per-user</help>
                <valueHelp>
                    <format>filename</format>
                    <description>Child directory of /config/auth e.g. /config/auth/ocserv/config-per-user</description>
                </valueHelp>
                <constraint>
                    <validator name="file-path" argument="--directory --parent-dir /config/auth --strict"/>
                </constraint>
            </properties>
        </leafNode>
        <leafNode name="default-config">
            <properties>
                <help>Default/fallback config to use when a file cannot be found in the configured directory that matches the username/group</help>
                <valueHelp>
                    <format>filename</format>
                    <description>Child directory of /config/auth e.g. /config/auth/ocserv/defaults/user.conf</description>
                </valueHelp>
                <constraint>
                    <validator name="file-path" argument="--file --parent-dir /config/auth --strict"/>
                </constraint>
            </properties>
        </leafNode>
        #include <include/generic-disable-node.xml.i>
    </children>
</node>
<!-- include end -->