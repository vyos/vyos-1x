(* In-process implementations of the most common validators, so validate-value
   can check a value without forking the external validator for every value.
   dispatch looks the validator up by basename; unknown validators return None
   and the caller falls back to running the external command. *)

(* numeric: same checks as numeric.ml, returning a result instead of exiting. *)
module Numeric = struct
  type numeric_str = Number_string of string | Range_string of string
  type numeric_val = Number_float of float | Range_float of float * float

  type options = {
    positive: bool;
    nonnegative: bool;
    allow_float: bool;
    ranges: string list;
    not_ranges: string list;
    not_values: string list;
    relative: bool;
    allow_range: bool;
    require_range: bool;
    parse_hex: bool;
    parse_oct: bool;
    parse_bin: bool;
    parse_dec: bool;
  }

  let default_opts = {
    positive = false;
    nonnegative = false;
    allow_float = false;
    ranges = [];
    not_ranges = [];
    not_values = [];
    relative = false;
    allow_range = false;
    require_range = false;
    parse_hex = false;
    parse_oct = false;
    parse_bin = false;
    parse_dec = false;
  }

  let parse_opts args =
    let rec aux o = function
      | [] -> o
      | "--non-negative" :: r -> aux {o with nonnegative=true} r
      | "--positive" :: r -> aux {o with positive=true} r
      | "--float" :: r -> aux {o with allow_float=true} r
      | "--relative" :: r -> aux {o with relative=true} r
      | "--allow-range" :: r -> aux {o with allow_range=true} r
      | "--require-range" :: r -> aux {o with require_range=true; allow_range=true} r
      | "--hex" :: r -> aux {o with parse_hex=true} r
      | "--octal" :: r -> aux {o with parse_oct=true} r
      | "--binary" :: r -> aux {o with parse_bin=true} r
      | "--decimal" :: r -> aux {o with parse_dec=true} r
      | "--range" :: v :: r -> aux {o with ranges=v :: o.ranges} r
      | "--not-range" :: v :: r -> aux {o with not_ranges=v :: o.not_ranges} r
      | "--not-value" :: v :: r -> aux {o with not_values=v :: o.not_values} r
      (* end-of-options marker (Arg.Rest in numeric.ml); the value is passed
         separately here, so stop parsing options *)
      | "--" :: _ -> o
      | u :: _ -> Printf.ksprintf failwith "Unknown numeric option '%s'" u
    in
    aux default_opts args

  let check_nonnegative opts m =
    if opts.nonnegative then
      match m with
      | Number_float n -> if n < 0.0 then failwith "Number should be non-negative."
      | Range_float _ -> failwith "option '--non-negative' does not apply to a range value"

  let check_positive opts m =
    if opts.positive then
      match m with
      | Number_float n -> if n <= 0.0 then failwith "Number should be positive"
      | Range_float _ -> failwith "option '--positive does' not apply to a range value"

  let looks_like_decimal value =
    try let _ = Pcre2.exec ~pat:"^(\\-?)[0-9]+(\\.[0-9]+)?$" value in true
    with Not_found -> false

  let looks_like_hex value =
    try let _ = Pcre2.exec ~pat:"^(\\-?)0[xX][0-9a-fA-F]+$" value in true
    with Not_found -> false

  let looks_like_octal value =
    try let _ = Pcre2.exec ~pat:"^(\\-?)0[oO][0-7]+$" value in true
    with Not_found -> false

  let looks_like_binary value =
    try let _ = Pcre2.exec ~pat:"^(\\-?)0[bB][0-1]+$" value in true
    with Not_found -> false

  let is_relative value =
    try let _ = Pcre2.exec ~pat:"^[+-](0[xboXBO])?[0-9a-fA-F]+$" value in true
    with Not_found -> false

  let number_string_drop_modifier value =
    String.sub value 1 (String.length value - 1)

  let get_relative opts t =
    if opts.relative then
      match t with
      | Number_string s ->
        if not (is_relative s) then failwith "Value is not a relative increment/decrement"
        else Number_string (number_string_drop_modifier s)
      | Range_string _ -> failwith "increment/decrement does not apply to a range value"
    else t

  let number_of_string opts s =
    if (opts.allow_float && not opts.parse_dec) then
      failwith "Only decimal numbers may be floating point"
    else if (opts.parse_hex && looks_like_hex s) ||
            (opts.parse_oct && looks_like_octal s) ||
            (opts.parse_bin && looks_like_binary s) then
      (match int_of_string_opt s with
       | Some n -> float_of_int n
       | None -> Printf.ksprintf failwith "'%s' is not a valid non-decimal number" s)
    else if (opts.parse_dec && looks_like_decimal s) then
      (match float_of_string_opt s with
       | Some n ->
         if opts.allow_float then n
         else if not (String.contains s '.') then n
         else Printf.ksprintf failwith "'%s' is not a valid integer number" s
       | None -> Printf.ksprintf failwith "'%s' is not a valid number" s)
    else Printf.ksprintf failwith "'%s' is not a valid number" s

  let range_of_string opts s =
    let param_opts = {opts with parse_dec=true} in
    let rs = String.split_on_char '-' s |> List.map String.trim |> List.map (number_of_string param_opts) in
    match rs with
    | [l; r] -> (l, r)
    | _ -> Printf.ksprintf failwith "'%s' is not a valid number range" s

  let value_in_ranges ranges n =
    let in_range (l, r) n = (n >= l) && (n <= r) in
    List.fold_left (fun acc r -> acc || (in_range r n)) false ranges

  let value_not_in_ranges ranges n =
    let in_range (l, r) n = (n >= l) && (n <= r) in
    List.fold_left (fun acc r -> acc && (not (in_range r n))) true ranges

  let check_ranges opts m =
    if opts.ranges <> [] then
      let ranges = List.map (range_of_string opts) opts.ranges in
      match m with
      | Number_float n ->
        if not (value_in_ranges ranges n) then failwith "Number is not in any of allowed ranges"
      | Range_float (i, j) ->
        if not (value_in_ranges ranges i) || not (value_in_ranges ranges j) then
          failwith "Range is not in any of allowed ranges"

  let check_not_ranges opts m =
    if opts.not_ranges <> [] then
      let ranges = List.map (range_of_string opts) opts.not_ranges in
      match m with
      | Number_float n ->
        if not (value_not_in_ranges ranges n) then failwith "Number is in one of excluded ranges"
      | Range_float (i, j) ->
        if not (value_not_in_ranges ranges i) || not (value_not_in_ranges ranges j) then
          failwith "Range is in one of excluded ranges"

  let check_not_values opts m =
    let param_opts = {opts with parse_dec=true} in
    let excluded = List.map (number_of_string param_opts) opts.not_values in
    if excluded = [] then () else
      match m with
      | Range_float _ -> failwith "--not-value cannot be used with ranges"
      | Number_float num ->
        (match List.find_opt ((=) num) excluded with
         | None -> ()
         | Some _ -> failwith "Value is excluded by --not-value")

  let check_argument_type opts m =
    match m with
    | Number_float _ -> if opts.require_range then failwith "Value must be a range, not a number"
    | Range_float _ -> if not opts.allow_range then failwith "Value must be a number, not a range"

  let is_range_val s =
    try let _ = Pcre2.exec ~pat:"^(0[xboXBO])?[0-9a-fA-F]+-(0[xboXBO])?[0-9a-fA-F]+$" s in true
    with Not_found -> false

  let var_numeric_str s = if is_range_val s then Range_string s else Number_string s

  let check_default_radix opts =
    if not opts.parse_hex && not opts.parse_oct && not opts.parse_bin
    then {opts with parse_dec=true} else opts

  let check args value =
    try
      let opts = check_default_radix (parse_opts args) in
      let s = get_relative opts (var_numeric_str value) in
      let n = match s with
        | Number_string r -> Number_float (number_of_string opts r)
        | Range_string r -> let i, j = range_of_string opts r in Range_float (i, j)
      in
      check_argument_type opts n;
      check_nonnegative opts n;
      check_positive opts n;
      check_not_values opts n;
      check_ranges opts n;
      check_not_ranges opts n;
      (true, "")
    with Failure err -> (false, err)
end

(* IPv4 helpers: a decimal octet, 0-255, no leading zeros (matches ipaddrcheck). *)
let octet_ok s =
  let n = String.length s in
  n >= 1 && n <= 3
  && String.for_all (fun c -> c >= '0' && c <= '9') s
  && not (n > 1 && s.[0] = '0')
  && (match int_of_string_opt s with Some v -> v <= 255 | None -> false)

let ipv4_address _args value =
  match String.split_on_char '.' value with
  | [a; b; c; d] when octet_ok a && octet_ok b && octet_ok c && octet_ok d -> (true, "")
  | _ -> (false, Printf.sprintf "%s is not a valid IPv4 address" value)

(* prefix length 0-32, no leading zeros *)
let plen_ok s =
  let n = String.length s in
  if n = 0 || not (String.for_all (fun c -> c >= '0' && c <= '9') s) then None
  else if n > 1 && s.[0] = '0' then None
  else match int_of_string_opt s with Some v when v <= 32 -> Some v | _ -> None

let ipv4_prefix _args value =
  let bad () = (false, Printf.sprintf "%s is not a valid IPv4 prefix" value) in
  match String.split_on_char '/' value with
  | [addr; plen] ->
    (match plen_ok plen, String.split_on_char '.' addr with
     | Some p, [a; b; c; d] when octet_ok a && octet_ok b && octet_ok c && octet_ok d ->
       let n = (int_of_string a lsl 24) lor (int_of_string b lsl 16)
               lor (int_of_string c lsl 8) lor (int_of_string d) in
       (* network address only: host bits must be zero *)
       if n land ((1 lsl (32 - p)) - 1) = 0 then (true, "") else bad ()
     | _ -> bad ())
  | _ -> bad ()

(* strict dotted-quad IPv4 to its 32-bit value *)
let ipv4_to_int value =
  match String.split_on_char '.' value with
  | [a; b; c; d] when octet_ok a && octet_ok b && octet_ok c && octet_ok d ->
    Some ((int_of_string a lsl 24) lor (int_of_string b lsl 16)
          lor (int_of_string c lsl 8) lor (int_of_string d))
  | _ -> None

(* ipaddrcheck --is-ipv4-range: two strict IPv4 singles joined by one hyphen,
   left <= right *)
let ipv4_range _args value =
  let bad () = (false, Printf.sprintf "%s is not a valid IPv4 address range" value) in
  match String.split_on_char '-' value with
  | [l; r] ->
    (match ipv4_to_int l, ipv4_to_int r with
     | Some ln, Some rn when ln <= rn -> (true, "")
     | _ -> bad ())
  | _ -> bad ()

(* IPv6 validators (ipv6-address, ipv6-prefix, ip-prefix) are intentionally not
   handled here: ipaddrcheck/libcidr accepts and rejects forms that a native
   parser cannot reproduce without changing behaviour, so they keep using the
   external validator. *)
let validators = [
  "numeric", Numeric.check;
  "ipv4-address", ipv4_address;
  "ipv4-prefix", ipv4_prefix;
  "ipv4-range", ipv4_range;
]

let dispatch cmd value =
  (* Whether a '-'-leading value is accepted depends on the validator's own
     option parsing (numeric only accepts it when the template ends in "--", via
     Arg.Rest), so defer such values to the external validator for an identical
     result. *)
  if String.length value > 0 && value.[0] = '-' then None
  else
    match String.split_on_char ' ' cmd |> List.filter (fun s -> s <> "") with
    | [] -> None
    | path :: args ->
      match List.assoc_opt (Filename.basename path) validators with
      | None -> None
      | Some f -> Some (f args value)
