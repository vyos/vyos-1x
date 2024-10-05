<!-- include start from dhcp/ddns-settings.xml.i -->
<leafNode name="send-updates">
<properties>
    <help>Send updates for this scope</help>
    <valueless/>
</properties>
</leafNode>
<leafNode name="override-client-update">
<properties>
    <help>Always update both forward and reverse DNS data, regardless of the client's request</help>
    <valueless/>
</properties>
</leafNode>
<leafNode name="override-no-update">
<properties>
    <help>Perform a DDNS update, even if the client instructs the server not to</help>
    <valueless/>
</properties>
</leafNode>
<leafNode name="replace-client-name">
<properties>
    <help>Replace client name mode</help>
    <completionHelp>
    <list>never always when-present when-not-present</list>
    </completionHelp>
    <valueHelp>
    <format>never</format>
    <description>Use the name the client sent. If the client sent no name, do not generate one. This is the default behavior</description>
    </valueHelp>
    <valueHelp>
    <format>always</format>
    <description>Replace the name the client sent. If the client sent no name, generate one for the client</description>
    </valueHelp>
    <valueHelp>
    <format>when-present</format>
    <description>Replace the name the client sent. If the client sent no name, do not generate one</description>
    </valueHelp>
    <valueHelp>
    <format>when-not-present</format>
    <description>Use the name the client sent. If the client sent no name, generate one for the client</description>
    </valueHelp>
    <constraint>
    <regex>(never|always|when-present|when-not-present)</regex>
    </constraint>
    <constraintErrorMessage>Invalid replace client name mode</constraintErrorMessage>
</properties>
</leafNode>
<leafNode name="generated-prefix">
<properties>
    <help>The prefix used in the generation of an FQDN</help>
    <constraint>
    <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid generated prefix</constraintErrorMessage>
</properties>
</leafNode>
<leafNode name="qualifying-suffix">
<properties>
    <help>The suffix used when generating an FQDN, or when qualifying a partial name</help>
    <constraint>
    <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Invalid qualifying suffix</constraintErrorMessage>
</properties>
</leafNode>
<leafNode name="update-on-renew">
<properties>
    <help>Update DNS record on lease renew</help>
    <valueless/>
</properties>
</leafNode>
<leafNode name="use-conflict-resolution">
<properties>
    <help>Defines DNS conflict resolution behavior</help>
    <valueless/>
</properties>
</leafNode>
<leafNode name="hostname-char-set">
<properties>
    <help>A regular expression describing the invalid character set in the host name</help>
</properties>
</leafNode>
<leafNode name="hostname-char-replacement">
<properties>
    <help>A string of zero or more characters with which to replace each invalid character in the host name</help>
</properties>
</leafNode>
<!-- include end -->
