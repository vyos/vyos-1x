(*
 *)
let intf_types = ref []
let broadcast = ref false
let bridgeable = ref false
let bondable = ref false
let no_vlan = ref false

let args = [
    ("--type", Arg.String (fun s -> intf_types := (s :: !intf_types)), "List interfaces of specified type");
    ("--broadcast", Arg.Unit (fun () -> broadcast := true), "List broadcast interfaces");
    ("--bridgeable", Arg.Unit (fun () -> bridgeable := true), "List bridgeable interfaces");
    ("--bondable", Arg.Unit (fun () -> bondable := true), "List bondable interfaces");
    ("--no-vlan-subinterfaces", Arg.Unit (fun () -> no_vlan := true), "List only parent interfaces");
]
let usage = Printf.sprintf "Usage: %s [OPTIONS] <number>" Sys.argv.(0)

let () = Arg.parse args (fun _ -> ()) usage

let type_to_prefix it =
    match it with
    | "" -> ""
    | "bonding" -> "bond"
    | "bridge" -> "br"
    | "dummy" -> "dum"
    | "ethernet" -> "eth"
    | "geneve" -> "gnv"
    | "input" -> "ifb"
    | "l2tpeth" -> "l2tpeth"
    | "loopback" -> "lo"
    | "macsec" -> "macsec"
    | "openvpn" -> "vtun"
    | "pppoe" -> "pppoe"
    | "pseudo-ethernet" -> "peth"
    | "sstpc" -> "sstpc"
    | "tunnel" -> "tun"
    | "virtual-ethernet" -> "veth"
    | "vti" -> "vti"
    | "vxlan" -> "vxlan"
    | "wireguard" -> "wg"
    | "wireless" -> "wlan"
    | "wwan" -> "wwan"
    | "zerotier" -> "zt"
    | _ -> ""

(* filter_section to match the constraint of python.vyos.ifconfig.section
 *)
let rx = Pcre2.regexp {|\d(\d|v|\.)*$|}

let filter_section s =
    let r = Pcre2.qreplace_first ~rex:rx ~templ:"" s in
    match r with
    |"bond"|"br"|"dum"|"eth"|"gnv"|"ifb"|"l2tpeth"|"lo"|"macsec" -> true
    |"peth"|"pppoe"|"sstpc"|"tun"|"veth"|"vti"|"vtun"|"vxlan"|"wg"|"wlan"|"wwan"|"zt" -> true
    | _ -> false

let filter_from_prefix p s =
    let pattern = Printf.sprintf "^%s(.*)$" p
    in
    try
        let _ = Pcre2.exec ~pat:pattern s in
        true
    with Not_found -> false

let filter_from_type it =
    let pre = type_to_prefix it in
    match pre with
    | "" -> None
    | _ -> Some (filter_from_prefix pre)

let filter_broadcast s =
    let pattern = {|^(bond|br|tun|vtun|eth|gnv|peth|macsec|veth|vxlan|wwan|wlan|zt)(.*)$|}
    in
    try
        let _ = Pcre2.exec ~pat:pattern s in
        true
    with Not_found -> false

let filter_bridgeable s =
    let pattern = {|^(bond|eth|gnv|l2tpeth|lo|tun|veth|vtun|vxlan|wlan|zt)(.*)$|}
    in
    try
        let _ = Pcre2.exec ~pat:pattern s in
        true
    with Not_found -> false

let filter_bondable s =
    let pattern = {|^(eth|lan|eno|ens)[A-Za-z0-9_-]*$|}
    in
    try
        let _ = Pcre2.exec ~pat:pattern s in
        true
    with Not_found -> false

let filter_no_vlan s =
    let pattern = {|^([^.]+)(\.\d+)+$|}
    in
    try
        let _ = Pcre2.exec ~pat:pattern s in
        false
    with Not_found -> true

let get_interfaces_by_type out intf_type =
    let fltr =
    if String.length(intf_type) > 0 then
        filter_from_type intf_type
    else None
    in
    let l = Func.list_interfaces () in
    let res = List.sort_uniq compare l in
    let res =
        if !broadcast then List.filter filter_broadcast res
        else res
    in
    let res =
        if !bridgeable then List.filter filter_bridgeable res
        else res
    in
    let res =
        if !bondable then List.filter filter_bondable res
        else res
    in
    let res =
        if !no_vlan then List.filter filter_no_vlan res
        else res
    in
    let add_out =
        let res = List.filter filter_section res in
        match fltr with
        | Some f -> List.filter f res
        | None -> res
    in List.append out add_out

let get_interfaces =
    let types = List.rev !intf_types in
    if types <> [] then
        List.fold_left get_interfaces_by_type [] types
    else
        get_interfaces_by_type [] ""

let () =
  let res = get_interfaces in
  List.iter (Printf.printf "%s ") res;
  Printf.printf "\n"
