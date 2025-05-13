(* Extract and validate the scheme part.
   As per the RFC:

  Scheme names consist of a sequence of characters. The lower case
  letters "a"--"z", digits, and the characters plus ("+"), period
  ("."), and hyphen ("-") are allowed. For resiliency, programs
  interpreting URLs should treat upper case letters as equivalent to
  lower case in scheme names (e.g., allow "HTTP" as well as "http").
 *)
let split_scheme url =
  let aux url =
    let res = Pcre2.exec ~pat:{|^([a-zA-Z0-9\.\-]+):(.*)$|} url in
    let scheme = Pcre2.get_substring res 1 in
    let uri = Pcre2.get_substring res 2 in
    (String.lowercase_ascii scheme, uri)
  in
  try Ok (aux url)
  with Not_found -> Error (Printf.sprintf {|"%s" is not a valid URL|} url)

let is_scheme_allowed allowed_schemes scheme =
  match List.find_opt ((=) scheme) allowed_schemes with
  | Some _ -> Ok ()
  | None -> Error (Printf.sprintf {|URL scheme "%s:" is not allowed|} scheme)

let regex_matches regex s =
  try
    let _ = Pcre2.exec ~rex:regex s in
    true
  with Not_found -> false

let host_path_format =
  Pcre2.regexp
  {|^//(?:[^/?#]+(?::[^/?#]*)?@)?([a-zA-Z0-9\-\._~]+|\[[a-zA-Z0-9:\.]+\])(?::([0-9]+))?(/.*)?$|}

let host_name_format = Pcre2.regexp {|^[a-zA-Z0-9]+([\-\._~]{1}[a-zA-Z0-9]+)*$|}
let ipv4_addr_format = Pcre2.regexp {|^(([1-9]\d{0,2}|0)\.){3}([1-9]\d{0,2}|0)$|}
let ipv6_addr_format = Pcre2.regexp {|^\[([a-z0-9:\.]+|[A-Z0-9:\.]+)\]$|}

let is_port s =
  try
    let n = int_of_string s in
    if n > 0 && n < 65536 then true
    else false
  with Failure _ -> false

let is_ipv4_octet s =
  try
    let n = int_of_string s in
    if n >= 0 && n < 256 then true
    else false
  with Failure _ -> false

let is_ipv6_segment s =
  try
    let n = int_of_string ("0x" ^ s) in
    if n >= 0 && n < 65536 then true
    else false
  with Failure _ -> false

let is_ipv4_addr s =
  let res = Pcre2.exec ~rex:ipv4_addr_format s in
  let ipv4_addr_str = Pcre2.get_substring res 0 in
  let ipv4_addr_l = String.split_on_char '.' ipv4_addr_str in
  List.for_all is_ipv4_octet ipv4_addr_l

let is_ipv6_pure_addr s =
  let ipv6_addr_l = String.split_on_char ':' s in
  if List.length ipv6_addr_l > 8 || List.length ipv6_addr_l < 3 then false
  else
    let seg_str_l = List.filter (fun s -> String.length s > 0) ipv6_addr_l in
    List.for_all is_ipv6_segment seg_str_l

let is_ipv6_dual_addr s =
  let ipv6_addr_l = List.rev (String.split_on_char ':' s) in
  match ipv6_addr_l with
  | [] -> false
  | h::t ->
      if not (is_ipv4_addr h) then false
      else
        if List.length t > 6 || List.length t < 2 then false
        else
          let seg_str_l = List.filter (fun s -> String.length s > 0) t in
          List.for_all is_ipv6_segment seg_str_l

let is_ipv6_addr s =
  let res = Pcre2.exec ~rex:ipv6_addr_format s in
  let ipv6_addr_str = Pcre2.get_substring res 1 in
  try
    let typo = Pcre2.exec ~pat:{|:::|} ipv6_addr_str in
    match typo with
    | _ -> false
  with Not_found ->
    is_ipv6_pure_addr ipv6_addr_str || is_ipv6_dual_addr ipv6_addr_str

let host_path_matches s =
  try
    let res = Pcre2.exec ~rex:host_path_format s in
    let substr = Pcre2.get_substrings ~full_match:false res in
    let port_str = Array.get substr 1 in
    if String.length port_str > 0 && not (is_port port_str) then false
    else
      let host = Array.get substr 0 in
      match host with
      | host when regex_matches ipv6_addr_format host -> is_ipv6_addr host
      | host when regex_matches ipv4_addr_format host -> is_ipv4_addr host
      | host when regex_matches host_name_format host -> true
      | _ -> false
  with Not_found -> false

let validate_uri scheme uri =
  if host_path_matches uri then Ok ()
  else Error (Printf.sprintf {|"%s" is not a valid URI for the %s URL scheme|} uri scheme)

let validate_url allowed_schemes url =
  let (let*) = Result.bind in
  let* scheme, uri = split_scheme url in
  let* () = is_scheme_allowed allowed_schemes scheme in
  let* () = validate_uri scheme uri in
  Ok ()

let file_transport_schemes = ["http"; "https"; "ftp"; "sftp"; "scp"; "tftp"]

let message_schemes = ["mailto"; "tel"; "sms"]

let allowed_schemes = ref []
let url = ref ""

let args = [
    ("--scheme",
     Arg.String (fun s -> allowed_schemes := s :: !allowed_schemes),
     "Allow only specified schemes");
    ("--file-transport",
     Arg.Unit (fun () -> allowed_schemes := (List.append !allowed_schemes file_transport_schemes)),
     "Allow only file transport protocols (HTTP/S, FTP, SCP/SFTP, TFTP)");
    ("--", Arg.Rest (fun s -> url := s), "Interpret next item as an argument");
]

let usage = Printf.sprintf "Usage: %s [OPTIONS] <URL>" Sys.argv.(0)

let () =
  let () = Arg.parse args (fun s -> url := s) usage in
  (* Force all allowed scheme named to lowercase for ease of comparison. *)
  let allowed_schemes = List.map String.lowercase_ascii !allowed_schemes in
  let res = validate_url allowed_schemes !url in
  match res with
  | Ok () -> ()
  | Error msg ->
    let () = Printf.fprintf stdout "%s" msg in
    exit 1
