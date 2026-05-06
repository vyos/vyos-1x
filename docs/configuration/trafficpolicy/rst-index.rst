.. _qos:

##############
Traffic Policy
##############


***
QoS
***

The generic name of Quality of Service or Traffic Control involves
things like shaping traffic, scheduling or dropping packets, which
are the kind of things you may want to play with when you have, for
instance, a bandwidth bottleneck in a link and you want to somehow
prioritize some type of traffic over another.

tc_ is a powerful tool for Traffic Control found at the Linux kernel.
However, its configuration is often considered a cumbersome task.
Fortunately, VyOS eases the job through its CLI, while using ``tc`` as
backend.


How to make it work
===================

In order to have VyOS Traffic Control working you need to follow 2
steps:

 1. **Create a traffic policy**.

 2. **Apply the traffic policy to an interface ingress or egress**.
    

But before learning to configure your policy, we will warn you
about the different units you can use and also show you what *classes*
are and how they work, as some policies may require you to configure
them.


Units
=====

When configuring your traffic policy, you will have to set data rate
values, watch out the units you are managing, it is easy to get confused
with the different prefixes and suffixes you can use. VyOS will always
show you the different units you can use.

Prefixes
--------

They can be **decimal** prefixes.

   .. code-block:: none

    kbit  (10^3)    kilobit per second
    mbit  (10^6)    megabit per second
    gbit  (10^9)    gigabit per second
    tbit  (10^12)   terabit per second
    
    kbps  (8*10^3)  kilobyte per second
    mbps  (8*10^6)  megabyte per second
    gbps  (8*10^9)  gigabyte per second
    tbps  (8*10^12) terabyte per second

Or **binary** prefixes.

   .. code-block:: none

    kibit (2^10 = 1024)    kibibit per second
    mibit (2^20 = 1024^2)  mebibit per second
    gibit (2^30 = 1024^3)  gibibit per second
    tbit  (2^40 = 1024^4)  tebibit per second

    kibps (1024*8)         kibibyte (KiB) per second
    mibps (1024^2*8)       mebibyte (MiB) per second
    gibps (1024^3*8)       gibibyte (GiB) per second
    tibps (1024^4*8)       tebibyte (TiB) per second


Suffixes
--------

A *bit* is written as **bit**,
   
   .. code-block:: none

        kbit (kilobits per second)
        mbit (megabits per second)
        gbit (gigabits per second)
        tbit (terabits per second)

while a *byte* is written as a single **b**.

   .. code-block:: none

        kbps (kilobytes per second)
        mbps (megabytes per second)
        gbps (gigabytes per second)




.. _classes:

Classes
=======

In the :ref:`creating_a_traffic_policy` section you will see that
some of the policies use *classes*. Those policies let you distribute
traffic into different classes according to different parameters you can
choose. So, a class is just a specific type of traffic you select.

The ultimate goal of classifying traffic is to give each class a
different treatment.


Matching traffic
----------------

In order to define which traffic goes into which class, you define
filters (that is, the matching criteria). Packets go through these matching
rules (as in the rules of a firewall) and, if a packet matches the filter, it
is assigned to that class.

In VyOS, a class is identified by a number you can choose when
configuring it.


.. note:: The meaning of the Class ID is not the same for every type of
   policy. Normally policies just need a meaningless number to identify
   a class (Class ID), but that does not apply to every policy.
   The number of a class in a Priority Queue it does not only
   identify it, it also defines its priority.


.. stop_vyoslinter

.. code-block:: none

  set qos policy <policy> <policy-name> class <class-ID> match <class-matching-rule-name>

.. start_vyoslinter

In the command above, we set the type of policy we are going to
work with and the name we choose for it; a class (so that we can
differentiate some traffic) and an identifiable number for that class;
then we configure a matching rule (or filter) and a name for it.

A class can have multiple match filters:

.. code-block:: none

  set qos policy shaper MY-SHAPER class 30 match HTTP
  set qos policy shaper MY-SHAPER class 30 match HTTPs

A match filter can contain multiple criteria and will match traffic if
all those criteria are true.

For example:

.. code-block:: none

  set qos policy shaper MY-SHAPER class 30 match HTTP ip protocol tcp
  set qos policy shaper MY-SHAPER class 30 match HTTP ip source port 80

This will match TCP traffic with source port 80.

There are many parameters you will be able to use in order to match the
traffic you want for a class:

 - **Ethernet (protocol, destination address or source address)**
 - **Interface name**
 - **IPv4 (DSCP value, maximum packet length, protocol, source address,**
   **destination address, source port, destination port or TCP flags)**
 - **IPv6 (DSCP value, maximum payload length, protocol, source address,**
   **destination address, source port, destination port or TCP flags)**
 - **Firewall mark**
 - **VLAN ID**

When configuring your filter, you can use the ``Tab`` key to see the many
different parameters you can configure.


.. code-block:: none

   vyos@vyos# set qos policy shaper MY-SHAPER class 30 match MY-FIRST-FILTER 
   Possible completions:
      description  Description
    > ether        Ethernet header match
      interface    Interface to use
    > ip           Match IP protocol header
    > ipv6         Match IPV6 protocol header
      mark         Match on mark applied by firewall
      vif          Virtual Local Area Network (VLAN) ID for this match
 
 

As shown in the example above, one of the possibilities to match packets
is based on marks done by the firewall,
`that can give you a great deal of flexibility`_.

You can also write a description for a filter:

.. stop_vyoslinter

.. code-block:: none

  set qos policy shaper MY-SHAPER class 30 match MY-FIRST-FILTER description "My filter description"

.. start_vyoslinter



.. note:: An IPv4 TCP filter will only match packets with an IPv4 header
   length of 20 bytes (which is the majority of IPv4 packets anyway).


.. note:: IPv6 TCP filters will only match IPv6 packets with no header
   extension, see https://en.wikipedia.org/wiki/IPv6_packet#Extension_headers

Traffic Match Group 
-------------------
In some case where we need to have an organization of our matching selection, 
in order to be more flexible and organize with our filter definition. We can 
apply traffic match groups, allowing us to create distinct filter groups within 
our policy and define various parameters for each group:

.. code-block:: none

  set qos traffic-match-group <group_name> match <match_name> 
  Possible completions:
     description          Description
   > ip                   Match IP protocol header
   > ipv6                 Match IPv6 protocol header
     mark                 Match on mark applied by firewall
     vif                  Virtual Local Area Network (VLAN) ID for this match

inherit matches from another group

.. code-block:: none

  set qos traffic-match-group <group_name> match-group <match_group_name> 

A match group can contain multiple criteria and inherit them in the same policy.

For example:

.. code-block:: none

  set qos traffic-match-group Mission-Critical match AF31 ip dscp 'AF31'
  set qos traffic-match-group Mission-Critical match AF32 ip dscp 'AF42'
  set qos traffic-match-group Mission-Critical match CS3 ip dscp 'CS3'
  set qos traffic-match-group Streaming-Video match AF11 ip dscp 'AF11'
  set qos traffic-match-group Streaming-Video match AF41 ip dscp 'AF41'
  set qos traffic-match-group Streaming-Video match AF43 ip dscp 'AF43'
  set qos policy shaper VyOS-HTB class 10 bandwidth '30%'
  set qos policy shaper VyOS-HTB class 10 description 'Multimedia'
  set qos policy shaper VyOS-HTB class 10 match CS4 ip dscp 'CS4'
  set qos policy shaper VyOS-HTB class 10 match-group 'Streaming-Video'
  set qos policy shaper VyOS-HTB class 10 priority '1'
  set qos policy shaper VyOS-HTB class 10 queue-type 'fair-queue'
  set qos policy shaper VyOS-HTB class 20 description 'MC'
  set qos policy shaper VyOS-HTB class 20 match-group 'Mission-Critical'
  set qos policy shaper VyOS-HTB class 20 priority '2'
  set qos policy shaper VyOS-HTB class 20 queue-type 'fair-queue'
  set qos policy shaper VyOS-HTB default bandwidth '20%'
  set qos policy shaper VyOS-HTB default queue-type 'fq-codel'

In this example, we can observe that different DSCP criteria are defined based 
on our QoS configuration within the same policy group.

Default
-------

Often you will also have to configure your *default* traffic in the same
way you do with a class. *Default* can be considered a class as it
behaves like that. It contains any traffic that did not match any
of the defined classes, so it is like an open class, a class without
matching filters.


Class treatment
---------------

Once a class has a filter configured, you will also have to define what
you want to do with the traffic of that class, what specific
Traffic-Control treatment you want to give it. You will have different
possibilities depending on the Traffic Policy you are configuring.

.. stop_vyoslinter

.. code-block:: none

   vyos@vyos# set qos policy shaper MY-SHAPER class 30
   Possible completions:
      bandwidth    Available bandwidth for this policy (default: auto)
      burst        Burst size for this class (default: 15k)
      ceiling      Bandwidth limit for this class
      codel-quantum
                   Deficit in the fair queuing algorithm (default 1514)
      description  Description
      flows        Number of flows into which the incoming packets are classified(default 1024)
      interval     Interval used to measure the delay (default 100)
   +> match        Class matching rule name
      priority     Priority for rule evaluation
      queue-limit  Maximum queue size
      queue-type   Queue type for default traffic (default: fq-codel)
      set-dscp     Change the Differentiated Services (DiffServ) field in the IP header
      target       Acceptable minimum standing/persistent queue delay (default: 5)

.. start_vyoslinter

For instance, with :code:`set qos policy shaper MY-SHAPER
class 30 set-dscp EF` you would be modifying the DSCP field value of packets in
that class to Expedite Forwarding.


  DSCP values as per :rfc:`2474` and :rfc:`4595`:

  +---------+------------+--------+------------------------------+
  | Binary  | Configured |  Drop  | Description                  |
  | value   | value      |  rate  |                              |
  +=========+============+========+==============================+
  | 101110  |     46     |   -    | Expedited forwarding (EF)    |
  +---------+------------+--------+------------------------------+
  | 000000  |     0      |   -    | Best effort traffic, default |
  +---------+------------+--------+------------------------------+
  | 001010  |     10     | Low    | Assured Forwarding(AF) 11    |
  +---------+------------+--------+------------------------------+
  | 001100  |     12     | Medium | Assured Forwarding(AF) 12    |
  +---------+------------+--------+------------------------------+
  | 001110  |     14     | High   | Assured Forwarding(AF) 13    |
  +---------+------------+--------+------------------------------+
  | 010010  |     18     | Low    | Assured Forwarding(AF) 21    |
  +---------+------------+--------+------------------------------+
  | 010100  |     20     | Medium | Assured Forwarding(AF) 22    |
  +---------+------------+--------+------------------------------+
  | 010110  |     22     | High   | Assured Forwarding(AF) 23    |
  +---------+------------+--------+------------------------------+
  | 011010  |     26     | Low    | Assured Forwarding(AF) 31    |
  +---------+------------+--------+------------------------------+
  | 011100  |     28     | Medium | Assured Forwarding(AF) 32    |
  +---------+------------+--------+------------------------------+
  | 011110  |     30     | High   | Assured Forwarding(AF) 33    |
  +---------+------------+--------+------------------------------+
  | 100010  |     34     | Low    | Assured Forwarding(AF) 41    |
  +---------+------------+--------+------------------------------+
  | 100100  |     36     | Medium | Assured Forwarding(AF) 42    |
  +---------+------------+--------+------------------------------+
  | 100110  |     38     | High   | Assured Forwarding(AF) 43    |
  +---------+------------+--------+------------------------------+




.. _embed:

Embedding one policy into another one
-------------------------------------

Often we need to embed one policy into another one. It is possible to do
so on classful policies, by attaching a new policy into a class. For
instance, you might want to apply different policies to the different
classes of a Round-Robin policy you have configured.

A common example is the case of some policies which, in order to be
effective, they need to be applied to an interface that is directly
connected where the bottleneck is. If your router is not
directly connected to the bottleneck, but some hop before it, you can
emulate the bottleneck by embedding your non-shaping policy into a
classful shaping one so that it takes effect.

You can configure a policy into a class through the ``queue-type``
setting.

.. code-block:: none

   set qos policy shaper FQ-SHAPER bandwidth 4gbit
   set qos policy shaper FQ-SHAPER default bandwidth 100%
   set qos policy shaper FQ-SHAPER default queue-type fq-codel

As shown in the last command of the example above, the `queue-type`
setting allows these combinations. You will be able to use it
in many policies.

.. note:: Some policies already include other embedded policies inside.
   That is the case of Shaper_: each of its classes use fair-queue
   unless you change it.

.. _creating_a_traffic_policy:


Creating a traffic policy
=========================

VyOS lets you control traffic in many different ways, here we will cover
every possibility. You can configure as many policies as you want, but
you will only be able to apply one policy per interface and direction
(inbound or outbound).

Some policies can be combined, you will be able to embed_ a different
policy that will be applied to a class of the main policy. 

.. hint:: **If you are looking for a policy for your outbound traffic**
   but you don't know which one you need and you don't want to go
   through every possible policy shown here, **our bet is that highly
   likely you are looking for a** Shaper_ **policy and you want to**
   :ref:`set its queues <embed>` **as FQ-CoDel**.

Drop Tail
---------

| **Queueing discipline:** PFIFO (Packet First In First Out).
| **Applies to:** Outbound traffic.

This the simplest queue possible you can apply to your traffic. Traffic
must go through a finite queue before it is actually sent. You must
define how many packets that queue can contain.

When a packet is to be sent, it will have to go through that queue, so
the packet will be placed at the tail of it. When the packet completely
goes through it, it will be dequeued emptying its place in the queue and
being eventually handed to the NIC to be actually sent out.

Despite the Drop-Tail policy does not slow down packets, if many packets
are to be sent, they could get dropped when trying to get enqueued at
the tail. This can happen if the queue has still not been able to
release enough packets from its head.

This is the policy that requires the lowest resources for the same
amount of traffic. But **very likely you do not need it as you cannot
get much from it. Sometimes it is used just to enable logging.**

.. cfgcmd:: set qos policy drop-tail <policy-name> queue-limit
   <number-of-packets>

   Use this command to configure a drop-tail policy (PFIFO). Choose a
   unique name for this policy and the size of the queue by setting the
   number of packets it can contain (maximum 4294967295).


Fair Queue
----------

| **Queueing discipline:** SFQ (Stochastic Fairness Queuing).
| **Applies to:** Outbound traffic.

Fair Queue is a work-conserving scheduler which schedules the
transmission of packets based on flows, that is, it balances traffic
distributing it through different sub-queues in order to ensure
fairness so that each flow is able to send data in turn, preventing any
single one from drowning out the rest.


.. cfgcmd:: set qos policy fair-queue <policy-name>

   Use this command to create a Fair-Queue policy and give it a name.
   It is based on the Stochastic Fairness Queueing and can be applied to
   outbound traffic.

In order to separate traffic, Fair Queue uses a classifier based on
source address, destination address and source port. The algorithm
enqueues packets to hash buckets based on those tree parameters.
Each of these buckets should represent a unique flow. Because multiple
flows may get hashed to the same bucket, the hashing algorithm is
perturbed at configurable intervals so that the unfairness lasts only
for a short while. Perturbation may however cause some inadvertent
packet reordering to occur. An advisable value could be 10 seconds.

One of the uses of Fair Queue might be the mitigation of Denial of
Service attacks.

.. cfgcmd:: set qos policy fair-queue <policy-name> hash-interval <seconds>

   Use this command to define a Fair-Queue policy, based on the
   Stochastic Fairness Queueing, and set the number of seconds at which
   a new queue algorithm perturbation will occur (maximum 4294967295).

When dequeuing, each hash-bucket with data is queried in a round robin
fashion. You can configure the length of the queue.

.. cfgcmd:: set qos policy fair-queue <policy-name> queue-limit <limit>

   Use this command to define a Fair-Queue policy, based on the
   Stochastic Fairness Queueing, and set the number of maximum packets
   allowed to wait in the queue. Any other packet will be dropped.

.. note:: Fair Queue is a non-shaping (work-conserving) policy, so it
   will only be useful if your outgoing interface is really full. If it
   is not, VyOS will not own the queue and Fair Queue will have no
   effect. If there is bandwidth available on the physical link, you can
   embed_ Fair-Queue into a classful shaping policy to make sure it owns
   the queue.



.. _FQ-CoDel:

FQ-CoDel
--------

| **Queueing discipline** Fair/Flow Queue CoDel.
| **Applies to:** Outbound Traffic.

The FQ-CoDel policy distributes the traffic into 1024 FIFO queues and
tries to provide good service between all of them. It also tries to keep
the length of all the queues short.

FQ-CoDel fights bufferbloat and reduces latency without the need of
complex configurations. It has become the new default Queueing
Discipline for the interfaces of some GNU/Linux distributions.

It uses a stochastic model to classify incoming packets into
different flows and is used to provide a fair share of the bandwidth to
all the flows using the queue. Each flow is managed by the CoDel
queuing  discipline. Reordering within a flow is avoided since Codel
internally uses a FIFO queue.

FQ-CoDel is based on a modified Deficit Round Robin (DRR_) queue
scheduler with the CoDel Active Queue Management (AQM) algorithm
operating on each queue.


.. note:: FQ-Codel is a non-shaping (work-conserving) policy, so it
   will only be useful if your outgoing interface is really full. If it
   is not, VyOS will not own the queue and FQ-Codel will have no
   effect. If there is bandwidth available on the physical link, you can
   embed_ FQ-Codel into a classful shaping policy to make sure it owns
   the queue. If you are not sure if you need to embed your FQ-CoDel
   policy into a Shaper, do it.


FQ-CoDel is tuned to run ok with its default parameters at 10Gbit
speeds. It might work ok too at other speeds without configuring
anything, but here we will explain some cases when you might want to
tune its parameters.

When running it at 1Gbit and lower, you may want to reduce the
`queue-limit` to 1000 packets or less. In rates like 10Mbit, you may
want to set it to 600 packets.

If you are using FQ-CoDel embedded into Shaper_ and you have large rates
(100Mbit and above), you may consider increasing `quantum` to 8000 or
higher so that the scheduler saves CPU.

On low rates (below 40Mbit) you may want to tune `quantum` down to
something like 300 bytes.

At very low rates (below 3Mbit), besides tuning `quantum` (300 keeps
being ok) you may also want to increase `target` to something like 15ms
and increase `interval` to something around 150 ms.


.. cfgcmd:: set qos policy fq-codel <policy name> codel-quantum <bytes>

   Use this command to configure an fq-codel policy, set its name and
   the maximum number of bytes (default: 1514) to be dequeued from a
   queue at once.

.. cfgcmd:: set qos policy fq-codel <policy name> flows <number-of-flows>

   Use this command to configure an fq-codel policy, set its name and
   the number of sub-queues (default: 1024) into which packets are
   classified.

.. cfgcmd:: set qos policy fq-codel <policy name> interval <milliseconds>

   Use this command to configure an fq-codel policy, set its name and
   the time period used by the control loop of CoDel to detect when a
   persistent queue is developing, ensuring that the measured minimum
   delay does not become too stale (default: 100ms).

.. cfgcmd:: set qos policy fq-codel <policy-name> queue-limit
   <number-of-packets>

   Use this command to configure an fq-codel policy, set its name, and
   define a hard limit on the real queue size. When this limit is
   reached, new packets are dropped (default: 10240 packets).

.. cfgcmd:: set qos policy fq-codel <policy-name> target <milliseconds>

   Use this command to configure an fq-codel policy, set its name, and
   define the acceptable minimum standing/persistent queue delay. This
   minimum delay is identified by tracking the local minimum queue delay
   that packets experience (default: 5ms).


Example
^^^^^^^

A simple example of an FQ-CoDel policy working inside a Shaper one.


.. code-block:: none

   set qos policy shaper FQ-CODEL-SHAPER bandwidth 2gbit
   set qos policy shaper FQ-CODEL-SHAPER default bandwidth 100%
   set qos policy shaper FQ-CODEL-SHAPER default queue-type fq-codel



Limiter
-------

| **Queueing discipline:** Ingress policer.
| **Applies to:** Inbound traffic.

Limiter is one of those policies that uses classes_ (Ingress qdisc is
actually a classless policy but filters do work in it).

The limiter performs basic ingress policing of traffic flows. Multiple
classes of traffic can be defined and traffic limits can be applied to
each class. Although the policer uses a token bucket mechanism
internally, it does not have the capability to delay a packet as a
shaping mechanism does. Traffic exceeding the defined bandwidth limits
is directly dropped. A maximum allowed burst can be configured too.

You can configure classes (up to 4090) with different settings and a
default policy which will be applied to any traffic not matching any of
the configured classes.


.. note:: In the case you want to apply some kind of **shaping** to your
  **inbound** traffic, check the ingress-shaping_ section.


.. cfgcmd:: set qos policy limiter <policy-name> class <class ID> match
   <match-name> description <description>

   Use this command to configure an Ingress Policer, defining its name,
   a class identifier (1-4090), a class matching rule name and its
   description.


Once the matching rules are set for a class, you can start configuring
how you want matching traffic to behave.


.. cfgcmd:: set qos policy limiter <policy-name> class <class-ID> bandwidth
   <rate>

   Use this command to configure an Ingress Policer, defining its name,
   a class identifier (1-4090) and the maximum allowed bandwidth for
   this class.


.. cfgcmd:: set qos policy limiter <policy-name> class <class-ID> burst
   <burst-size>

   Use this command to configure an Ingress Policer, defining its name,
   a class identifier (1-4090) and the burst size in bytes for this
   class (default: 15).


.. cfgcmd:: set qos policy limiter <policy-name> default bandwidth <rate>

   Use this command to configure an Ingress Policer, defining its name
   and the maximum allowed bandwidth for its default policy.


.. cfgcmd:: set qos policy limiter <policy-name> default burst <burst-size>

   Use this command to configure an Ingress Policer, defining its name
   and the burst size in bytes (default: 15) for its default policy.


.. cfgcmd:: set qos policy limiter <policy-name> class <class ID> priority
   <value>

   Use this command to configure an Ingress Policer, defining its name,
   a class identifier (1-4090), and the priority (0-20, default 20) in
   which the rule is evaluated (the lower the number, the higher the
   priority).

 

Network Emulator
----------------

| **Queueing discipline:** netem (Network Emulator) + TBF (Token Bucket Filter).
| **Applies to:** Outbound traffic.

VyOS Network Emulator policy emulates the conditions you can suffer in a
real network. You will be able to configure things like rate, burst,
delay, packet loss, packet corruption or packet reordering.

This could be helpful if you want to test how an application behaves
under certain network conditions.


.. cfgcmd:: set qos policy network-emulator <policy-name> bandwidth <rate>
   
   Use this command to configure the maximum rate at which traffic will
   be shaped in a Network Emulator policy. Define the name of the policy
   and the rate.

.. cfgcmd:: set qos policy network-emulator <policy-name> burst <burst-size>
   
   Use this command to configure the burst size of the traffic in a
   Network Emulator policy. Define the name of the Network Emulator
   policy and its traffic burst size (it will be configured through the
   Token Bucket Filter qdisc). Default:15kb. It will only take effect if
   you have configured its bandwidth too.

.. cfgcmd:: set qos policy network-emulator <policy-name> delay
   <delay>
   
   Use this command to configure a Network Emulator policy defining its
   name and the fixed amount of time you want to add to all packet going
   out of the interface. The latency will be added through the
   Token Bucket Filter qdisc. It will only take effect if you have
   configured its bandwidth too. You can use secs, ms and us. Default:
   50ms.

.. cfgcmd:: set qos policy network-emulator <policy-name> corruption
   <percent>
   
   Use this command to emulate noise in a Network Emulator policy. Set
   the policy name and the percentage of corrupted packets you want. A
   random error will be introduced in a random position for the chosen
   percent of packets.

.. cfgcmd:: set qos policy network-emulator <policy-name> loss
   <percent>
   
   Use this command to emulate packet-loss conditions in a Network
   Emulator policy. Set the policy name and the percentage of loss
   packets your traffic will suffer.

.. cfgcmd:: set traffic-policy network-emulator <policy-name> reordering
   <percent>
   
   Use this command to emulate packet-reordering conditions in a Network
   Emulator policy. Set the policy name and the percentage of reordered
   packets your traffic will suffer.

.. cfgcmd:: set traffic-policy network-emulator <policy-name> queue-limit
   <limit>
   
   Use this command to define the length of the queue of your Network
   Emulator policy. Set the policy name and the maximum number of
   packets (1-4294967295) the queue may hold queued at a time.



Priority Queue
--------------

| **Queueing discipline:** PRIO.
| **Applies to:** Outbound traffic.


The Priority Queue is a classful scheduling policy. It does not delay
packets (Priority Queue is not a shaping policy), it simply dequeues
packets according to their priority.

.. note:: Priority Queue, as other non-shaping policies, is only useful
   if your outgoing interface is really full. If it is not, VyOS will
   not own the queue and Priority Queue will have no effect. If there is
   bandwidth available on the physical link, you can embed_ Priority
   Queue into a classful shaping policy to make sure it owns the queue.
   In that case packets can be prioritized based on DSCP.

Up to seven queues -defined as classes_ with different priorities- can
be configured. Packets are placed into queues based on associated match
criteria. Packets are transmitted from the queues in priority order. If
classes with a higher priority are being filled with packets
continuously, packets from lower priority classes will only be
transmitted after traffic volume from higher priority classes decreases.


.. note:: In Priority Queue we do not define classes with a meaningless
   class ID number but with a class priority number (1-7). The lower the
   number, the higher the priority.


As with other policies, you can define different type of matching rules
for your classes:

.. code-block:: none

   vyos@vyos# set qos policy priority-queue MY-PRIO class 3 match MY-MATCH-RULE 
   Possible completions:
      description  Description
    > ether        Ethernet header match
      interface    Interface to use
    > ip           Match IP protocol header
    > ipv6         Match IPV6 protocol header
      mark         Match on mark applied by firewall
      vif          Virtual Local Area Network (VLAN) ID for this match


As with other policies, you can embed_ other policies into the classes 
(and default) of your Priority Queue policy through the ``queue-type``
setting:

.. code-block:: none

   vyos@vyos# set qos policy priority-queue MY-PRIO class 3 queue-type 
   Possible completions:
      drop-tail    First-In-First-Out (FIFO) (default)
      fq-codel     Fair Queue Codel
      fair-queue   Stochastic Fair Queue (SFQ)
      priority     Priority queueing
      random-detect
                   Random Early Detection (RED)


.. cfgcmd:: set qos policy priority-queue <policy-name> class <class-ID> 
   queue-limit <limit>

   Use this command to configure a Priority Queue policy, set its name,
   set a class with a priority from 1 to 7 and define a hard limit on
   the real queue size. When this limit is reached, new packets are
   dropped.



.. _Random-Detect:

Random-Detect
-------------


| **Queueing discipline:** Generalized Random Early Drop.
| **Applies to:** Outbound traffic.

A simple Random Early Detection (RED) policy would start randomly
dropping packets from a queue before it reaches its queue limit thus
avoiding congestion. That is good for TCP connections as the gradual
dropping of packets acts as a signal for the sender to decrease its
transmission rate.

In contrast to simple RED, VyOS' Random-Detect uses a Generalized Random
Early Detect policy that provides different virtual queues based on the
IP Precedence value so that some virtual queues can drop more packets
than others. 

This is achieved by using the first three bits of the ToS (Type of
Service) field to categorize data streams and, in accordance with the
defined precedence parameters, a decision is made.

IP precedence as defined in :rfc:`791`:

 +------------+----------------------+
 | Precedence |      Priority        |
 +============+======================+
 |      7     | Network Control      |
 +------------+----------------------+
 |      6     | Internetwork Control |
 +------------+----------------------+
 |      5     | CRITIC/ECP           |
 +------------+----------------------+
 |      4     | Flash Override       |
 +------------+----------------------+
 |      3     | Flash                |
 +------------+----------------------+
 |      2     | Immediate            |
 +------------+----------------------+
 |      1     | Priority             |
 +------------+----------------------+
 |      0     | Routine              |
 +------------+----------------------+


Random-Detect could be useful for heavy traffic. One use of this
algorithm might be to prevent a backbone overload. But only for TCP
(because dropped packets could be retransmitted), not for UDP.


.. cfgcmd:: set qos policy random-detect <policy-name> bandwidth <bandwidth>

   Use this command to configure a Random-Detect policy, set its name
   and set the available bandwidth for this policy. It is used for
   calculating the average queue size after some idle time. It should be
   set to the bandwidth of your interface. Random Detect is not a
   shaping policy, this command will not shape.

.. cfgcmd:: set qos policy random-detect <policy-name> precedence
   <IP-precedence-value> average-packet <bytes>
   
   Use this command to configure a Random-Detect policy and set its
   name, then state the IP Precedence for the virtual queue you are
   configuring and what the size of its average-packet should be
   (in bytes, default: 1024).

.. note:: When configuring a Random-Detect policy: **the higher the
   precedence number, the higher the priority**.

.. cfgcmd:: set qos policy random-detect <policy-name> precedence
   <IP-precedence-value> mark-probability <value>
   
   Use this command to configure a Random-Detect policy and set its
   name, then state the IP Precedence for the virtual queue you are
   configuring and what its mark (drop) probability will be. Set the
   probability by giving the N value of the fraction 1/N (default: 10).


.. cfgcmd:: set qos policy random-detect <policy-name> precedence
   <IP-precedence-value> maximum-threshold <packets>
   
   Use this command to configure a Random-Detect policy and set its
   name, then state the IP Precedence for the virtual queue you are
   configuring and what its maximum threshold for random detection will
   be (from 0 to 4096 packets, default: 18). At this size, the marking
   (drop) probability is maximal.

.. cfgcmd:: set qos policy random-detect <policy-name> precedence
   <IP-precedence-value> minimum-threshold <packets>
   
   Use this command to configure a Random-Detect policy and set its
   name, then state the IP Precedence for the virtual queue you are
   configuring and what its minimum threshold for random detection will
   be (from 0 to 4096 packets).  If this value is exceeded, packets
   start being eligible for being dropped.


The default values for the minimum-threshold depend on IP precedence:

 +------------+-----------------------+
 | Precedence | default min-threshold |
 +============+=======================+
 |      7     |         16            |
 +------------+-----------------------+
 |      6     |         15            |
 +------------+-----------------------+
 |      5     |         14            |
 +------------+-----------------------+
 |      4     |         13            |
 +------------+-----------------------+
 |      3     |         12            |
 +------------+-----------------------+
 |      2     |         11            |
 +------------+-----------------------+
 |      1     |         10            |
 +------------+-----------------------+
 |      0     |          9            |
 +------------+-----------------------+


.. cfgcmd:: set qos policy random-detect <policy-name> precedence
   <IP-precedence-value> queue-limit <packets>
   
   Use this command to configure a Random-Detect policy and set its
   name, then name the IP Precedence for the virtual queue you are
   configuring and what the maximum size of its queue will be (from 1 to
   1-4294967295 packets). Packets are dropped when the current queue
   length reaches this value.


If the average queue size is lower than the **min-threshold**, an
arriving packet will be placed in the queue.

In the case the average queue size is between **min-threshold** and
**max-threshold**, then an arriving packet would be either dropped or
placed in the queue, it will depend on the defined **mark-probability**.

If the current queue size is larger than **queue-limit**,
then packets will be dropped. The average queue size depends on its
former average size and its current one.

If **max-threshold** is set but **min-threshold is not, then
**min-threshold** is scaled to 50% of **max-threshold**.

In principle, values must be
:code:`min-threshold` < :code:`max-threshold` < :code:`queue-limit`.




Rate Control
------------

| **Queueing discipline:** Token Bucket Filter.
| **Applies to:** Outbound traffic.

Rate-Control is a classless policy that limits the packet flow to a set
rate. It is a pure shaper, it does not schedule traffic. Traffic is
filtered based on the expenditure of tokens. Tokens roughly correspond
to bytes.

Short bursts can be allowed to exceed the limit. On creation, the
Rate-Control traffic is stocked with tokens which correspond to the
amount of traffic that can be burst in one go. Tokens arrive at a steady
rate, until the bucket is full.

.. cfgcmd:: set qos policy rate-control <policy-name> bandwidth <rate>

   Use this command to configure a Rate-Control policy, set its name
   and the rate limit you want to have.

.. cfgcmd:: set qos policy rate-control <policy-name> burst <burst-size>

   Use this command to configure a Rate-Control policy, set its name
   and the size of the bucket in bytes which will be available for
   burst.


As a reference: for 10mbit/s on Intel, you might need at least 10kbyte
buffer if you want to reach your configured rate.

A very small buffer will soon start dropping packets.

.. cfgcmd:: set qos policy rate-control <policy-name> latency 

   Use this command to configure a Rate-Control policy, set its name
   and the maximum amount of time a packet can be queued (default: 50
   ms).


Rate-Control is a CPU-friendly policy. You might consider using it when
you just simply want to slow traffic down.

.. _DRR:

Round Robin
-----------

| **Queueing discipline:** Deficit Round Robin.
| **Applies to:** Outbound traffic.

The round-robin policy is a classful scheduler that divides traffic in
different classes_ you can configure (up to 4096). You can embed_ a
new policy into each of those classes (default included).
 
Each class is assigned a deficit counter (the number of bytes that a
flow is allowed to transmit when it is its turn) initialized to quantum.
Quantum is a parameter you configure which acts like a credit of fix
bytes the counter receives on each round. Then the Round-Robin policy
starts moving its Round Robin pointer through the queues. If the deficit
counter is greater than the packet's size at the head of the queue, this
packet will be sent and the value of the counter will be decremented by
the packet size. Then, the size of the next packet will be compared to
the counter value again, repeating the process. Once the queue is empty
or the value of the counter is insufficient, the Round-Robin pointer
will move to the next queue. If the queue is empty, the value of the
deficit counter is reset to 0. 

At every round, the deficit counter adds the quantum so that even large
packets will have their opportunity to be dequeued.


.. cfgcmd:: set qos policy round-robin <policy name> class
   <class-ID> quantum <packets>

   Use this command to configure a Round-Robin policy, set its name, set
   a class ID, and the quantum for that class. The deficit counter will
   add that value each round.

.. cfgcmd:: set qos policy round-robin <policy name> class
   <class ID> queue-limit <packets>

   Use this command to configure a Round-Robin policy, set its name, set
   a class ID, and the queue size in packets.

As with other policies, Round-Robin can embed_ another policy into a
class through the ``queue-type`` setting.

.. code-block:: none

   vyos@vyos# set qos policy round-robin DRR class 10 queue-type 
   Possible completions:
      drop-tail    First-In-First-Out (FIFO) (default)
      fq-codel     Fair Queue Codel
      fair-queue   Stochastic Fair Queue (SFQ)
      priority     Priority queueing based
      random-detect
                   Random Early Detection (RED)
            



.. _Shaper:

Shaper
------

| **Queueing discipline:** Hierarchical Token Bucket.
| **Applies to:** Outbound traffic.


The Shaper policy does not guarantee a low delay, but it does guarantee
bandwidth to different traffic classes and also lets you decide how to
allocate more traffic once the guarantees are met.

Each class can have a guaranteed part of the total bandwidth defined for
the whole policy, so all those shares together should not be higher
than the policy's whole bandwidth.

If guaranteed traffic for a class is met and there is room for more
traffic, the ceiling parameter can be used to set how much more
bandwidth could be used. If guaranteed traffic is met and there are
several classes willing to use their ceilings, the priority parameter
will establish the order in which that additional traffic will be
allocated. Priority can be any number from 0 to 7. The lower the number,
the higher the priority.


.. cfgcmd:: set qos policy shaper <policy-name> bandwidth <rate>

   Use this command to configure a Shaper policy, set its name
   and the maximum bandwidth for all combined traffic.


.. cfgcmd:: set qos policy shaper <policy-name> class <class-ID> bandwidth
   <rate>

   Use this command to configure a Shaper policy, set its name, define
   a class and set the guaranteed traffic you want to allocate to that
   class.

.. cfgcmd:: set qos policy shaper <policy-name> class <class-ID> burst
   <bytes>

   Use this command to configure a Shaper policy, set its name, define
   a class and set the size of the `tocken bucket`_ in bytes, which will
   be available to be sent at ceiling speed (default: 15Kb).

.. cfgcmd:: set qos policy shaper <policy-name> class <class-ID> ceiling
   <bandwidth>

   Use this command to configure a Shaper policy, set its name, define
   a class and set the maximum speed possible for this class. The
   default ceiling value is the bandwidth value.

.. cfgcmd:: set qos policy shaper <policy-name> class <class-ID> priority
   <0-7>

   Use this command to configure a Shaper policy, set its name, define
   a class and set the priority for usage of available bandwidth once
   guarantees have been met. The lower the priority number, the higher
   the priority. The default priority value is 0, the highest priority.


As with other policies, Shaper can embed_ other policies into its
classes through the ``queue-type`` setting and then configure their
parameters.


.. code-block:: none

   vyos@vyos# set qos policy shaper HTB class 10 queue-type 
   Possible completions:
      fq-codel     Fair Queue Codel (default)
      fair-queue   Stochastic Fair Queue (SFQ)
      drop-tail    First-In-First-Out (FIFO)
      priority     Priority queueing
      random-detect
                   Random Early Detection (RED)


.. stop_vyoslinter

.. code-block:: none

   vyos@vyos# set qos policy shaper HTB class 10
   Possible completions:
      bandwidth    Available bandwidth for this policy (default: auto)
      burst        Burst size for this class (default: 15k)
      ceiling      Bandwidth limit for this class
      codel-quantum
                   Deficit in the fair queuing algorithm (default 1514)
      description  Description
      flows        Number of flows into which the incoming packets are classified (default 1024)
      interval     Interval used to measure the delay (default 100)
   +> match        Class matching rule name
      priority     Priority for rule evaluation
      queue-limit  Maximum queue size (packets)
      queue-type   Queue type for default traffic (default: fq-codel)
      set-dscp     Change the Differentiated Services (DiffServ) field in the IP header
      target       Acceptable minimum standing/persistent queue delay (default: 5)

.. start_vyoslinter



.. note:: If you configure a class for **VoIP traffic**, don't give it any
   *ceiling*, otherwise new VoIP calls could start when the link is
   available and get suddenly dropped when other classes start using
   their assigned *bandwidth* share.

.. _traffic_policy:shaper_example:

Example
^^^^^^^

A simple example of Shaper using priorities.


.. stop_vyoslinter

.. code-block:: none

   set qos policy shaper MY-HTB bandwidth '50mbit'
   set qos policy shaper MY-HTB class 10 bandwidth '20%'
   set qos policy shaper MY-HTB class 10 match DSCP ip dscp 'EF'
   set qos policy shaper MY-HTB class 10 queue-type 'fq-codel'
   set qos policy shaper MY-HTB class 20 bandwidth '10%'
   set qos policy shaper MY-HTB class 20 ceiling '50%'
   set qos policy shaper MY-HTB class 20 match PORT666 ip destination port '666'
   set qos policy shaper MY-HTB class 20 priority '3'
   set qos policy shaper MY-HTB class 20 queue-type 'fair-queue'
   set qos policy shaper MY-HTB class 30 bandwidth '10%'
   set qos policy shaper MY-HTB class 30 ceiling '50%'
   set qos policy shaper MY-HTB class 30 match ADDRESS30 ip source address '192.168.30.0/24'
   set qos policy shaper MY-HTB class 30 priority '5'
   set qos policy shaper MY-HTB class 30 queue-type 'fair-queue'
   set qos policy shaper MY-HTB default bandwidth '10%'
   set qos policy shaper MY-HTB default ceiling '100%'
   set qos policy shaper MY-HTB default priority '7'
   set qos policy shaper MY-HTB default queue-type 'fair-queue'

.. start_vyoslinter

.. _CAKE:

CAKE
------

| **Queueing discipline:** Deficit mode.
| **Applies to:** Outbound traffic.

`Common Applications Kept Enhanced`_ (CAKE) is a comprehensive queue management
system, implemented as a queue discipline (qdisc) for the Linux kernel. It is
designed to replace and improve upon the complex hierarchy of simple qdiscs
presently required to effectively tackle the bufferbloat problem at the network
edge.

.. cfgcmd:: set qos policy cake <text> bandwidth <value>

   Set the shaper bandwidth, either as an explicit bitrate or a percentage
   of the interface bandwidth.

.. cfgcmd:: set qos policy cake <text> description

   Set a description for the shaper.

.. cfgcmd:: set qos policy cake <text> flow-isolation blind

   Disables flow isolation, all traffic passes through a single queue.

.. cfgcmd:: set qos policy cake <text> flow-isolation dst-host

   Flows are defined only by destination address.

.. cfgcmd:: set qos policy cake <text> flow-isolation dual-dst-host

   Flows are defined by the 5-tuple. Fairness is applied first over destination
   addresses, then over individual flows.

.. cfgcmd:: set qos policy cake <text> flow-isolation dual-src-host

   Flows are defined by the 5-tuple. Fairness is applied first over source
   addresses, then over individual flows.

.. cfgcmd:: set qos policy cake <text> flow-isolation flow

   Flows are defined by the entire 5-tuple (source IP address, source port,
   destination IP address, destination port, transport protocol).

.. cfgcmd:: set qos policy cake <text> flow-isolation host

   Flows are defined by source-destination host pairs.

.. cfgcmd:: set qos policy cake <text> flow-isolation nat

   Perform NAT lookup before applying flow-isolation rules.

.. cfgcmd:: set qos policy cake <text> flow-isolation src-host

   Flows are defined only by source address.

.. cfgcmd:: set qos policy cake <text> flow-isolation triple-isolate

   **(Default)** Flows are defined by the 5-tuple, fairness is applied
   over source and destination addresses and also over individual flows.

.. cfgcmd:: set qos policy cake <text> rtt

   Defines the round-trip time used for active queue management (AQM) in
   milliseconds. The default value is 100.


Applying a traffic policy
=========================

Once a traffic-policy is created, you can apply it to an interface:

.. code-block:: none

  set qos interface eth0 egress WAN-OUT

You can only apply one policy per interface and direction, but you could
reuse a policy on different interfaces and directions:

.. code-block:: none

  set qos interface eth0 ingress WAN-IN
  set qos interface eth0 egress WAN-OUT
  set qos interface eth1 ingress LAN-IN
  set qos interface eth1 egress LAN-OUT
  set qos interface eth2 ingress LAN-IN
  set qos interface eth2 egress LAN-OUT
  set qos interface eth3 ingress TWO-WAY-POLICY
  set qos interface eth3 egress TWO-WAY-POLICY
  set qos interface eth4 ingress TWO-WAY-POLICY
  set qos interface eth4 egress TWO-WAY-POLICY



.. _ingress-shaping:

The case of ingress shaping
===========================

| **Applies to:** Inbound traffic.

For the ingress traffic of an interface, there is only one policy you
can directly apply, a **Limiter** policy. You cannot apply a shaping
policy directly to the ingress traffic of any interface because shaping
only works for outbound traffic.

This workaround lets you apply a shaping policy to the ingress traffic
by first redirecting it to an in-between virtual interface
(`Intermediate Functional Block`_). There, in that virtual interface,
you will be able to apply any of the policies that work for outbound
traffic, for instance, a shaping one.

That is how it is possible to do the so-called "ingress shaping".


.. code-block:: none

   set qos policy shaper MY-INGRESS-SHAPING bandwidth 1000kbit
   set qos policy shaper MY-INGRESS-SHAPING default bandwidth 1000kbit
   set qos policy shaper MY-INGRESS-SHAPING default queue-type fair-queue
   
   set qos interface ifb0 egress MY-INGRESS-SHAPING
   set interfaces ethernet eth0 redirect ifb0

   set interfaces input ifb0

.. warning::

  Do not configure IFB as the first step. First create everything else
  of your traffic-policy, and then you can configure IFB.
  Otherwise you might get the ``RTNETLINK answer: File exists`` error,
  which can be solved with ``sudo ip link delete ifb0``.


.. stop_vyoslinter

.. _that can give you a great deal of flexibility: https://blog.vyos.io/using-the-policy-route-and-packet-marking-for-custom-qos-matches
.. _tc: https://en.wikipedia.org/wiki/Tc_(Linux)
.. _tocken bucket: https://en.wikipedia.org/wiki/Token_bucket
.. _HFSC: https://en.wikipedia.org/wiki/Hierarchical_fair-service_curve
.. _Intermediate Functional Block: https://www.linuxfoundation.org/collaborate/workgroups/networking/ifb
.. _Common Applications Kept Enhanced: https://www.bufferbloat.net/projects/codel/wiki/Cake/

.. start_vyoslinter
