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
}

let opts = ref default_opts

let number_arg = ref ""

let args = [
    ("--non-negative", Arg.Unit (fun () -> opts := {!opts with nonnegative=true}), "Check if the number is non-negative (>= 0)");
    ("--positive", Arg.Unit (fun () -> opts := {!opts with positive=true}), "Check if the number is positive (> 0)");
    ("--range", Arg.String (fun s -> let optsv = !opts in opts := {optsv with ranges=(s :: optsv.ranges)}), "Check if the number or range is within a range (inclusive)");
    ("--not-range", Arg.String (fun s -> let optsv = !opts in opts := {optsv with not_ranges=(s :: optsv.not_ranges)}), "Check if the number or range is not within a range (inclusive)");
    ("--not-value", Arg.String (fun s -> let optsv = !opts in opts := {optsv with not_values=(s :: optsv.not_values)}), "Check if the number does not equal a specific value");
    ("--float", Arg.Unit (fun () -> opts := {!opts with allow_float=true}), "Allow floating-point numbers");
    ("--relative", Arg.Unit (fun () -> opts := {!opts with relative=true}), "Allow relative increment/decrement (+/-N)");
    ("--allow-range", Arg.Unit (fun () -> opts := {!opts with allow_range=true}), "Allow the argument to be a range rather than a single number");
    ("--require-range", Arg.Unit (fun () -> opts := {!opts with require_range=true; allow_range=true}), "Require the argument to be a range rather than a single number");
    ("--", Arg.Rest (fun s -> number_arg := s), "Interpret next item as an argument");
]
let usage = Printf.sprintf "Usage: %s [OPTIONS] <number>|<range>" Sys.argv.(0)

let () = if Array.length Sys.argv = 1 then (Arg.usage args usage; exit 1)
let () = Arg.parse args (fun s -> number_arg := s) usage

let check_nonnegative opts m =
  if opts.nonnegative then
    match m with
    | Number_float n ->
        if (n < 0.0) then
          failwith "Number should be non-negative."
    | Range_float _ ->
        failwith "option '--non-negative' does not apply to a range value"

let check_positive opts m =
  if opts.positive then
    match m with
    | Number_float n ->
        if (n <= 0.0) then
          failwith "Number should be positive"
    | Range_float _ ->
        failwith "option '--positive does' not apply to a range value"

let looks_like_number value =
  try let _ = Pcre2.exec ~pat:"^(\\-?)[0-9]+(\\.[0-9]+)?$" value in true
  with Not_found -> false

let is_relative value =
  try let _ = Pcre2.exec ~pat:"^[+-][0-9]+$" value in true
  with Not_found -> false

let number_string_drop_modifier value =
  String.sub value 1 (String.length value - 1)

let get_relative opts t =
  if opts.relative then
    match t with
    | Number_string s ->
        if not (is_relative s) then
          failwith "Value is not a relative increment/decrement"
        else Number_string (number_string_drop_modifier s)
    | Range_string _ ->
        failwith "increment/decrement does not apply to a range value"
  else t

let number_of_string opts s =
  if not (looks_like_number s) then Printf.ksprintf failwith "'%s' is not a valid number" s else
  let n = float_of_string_opt s in
  match n with
  | Some n ->
    (* If floats are explicitly allowed, just return the number. *)
    if opts.allow_float then n
    (* If floats are not explicitly allowed, check if the argument has a decimal separator in it.
       If the argument string contains a dot but float_of_string didn't dislike it,
       it's a valid number but not an integer.
     *)
    else if not (String.contains s '.') then n
    (* If float_of_string returned None, the argument string is just garbage rather than a number. *)
    else Printf.ksprintf failwith "'%s' is not a valid integer number" s
  | None ->
     Printf.ksprintf failwith "'%s' is not a valid number" s

let range_of_string opts s =
  let rs = String.split_on_char '-' s |> List.map String.trim |> List.map (number_of_string opts) in
  match rs with
  | [l; r] -> (l, r)
  | exception (Failure msg) ->
    (* Some of the numbers in the range are bad. *)
    Printf.ksprintf failwith "'%s' is not a valid number range: %s" s msg
  | _ ->
    (* The range itself if malformed, like 1-10-20. *)
    Printf.ksprintf failwith "'%s' is not a valid number range" s

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
        if not (value_in_ranges ranges n) then
          Printf.ksprintf failwith "Number is not in any of allowed ranges"
    | Range_float (i, j) ->
        if (not (value_in_ranges ranges i) ||
            not (value_in_ranges ranges j)) then
              Printf.ksprintf failwith "Range is not in any of allowed ranges"


let check_not_ranges opts m =
  if opts.not_ranges <> [] then
    let ranges = List.map (range_of_string opts) opts.not_ranges in
    match m with
    | Number_float n ->
        if not (value_not_in_ranges ranges n) then
          Printf.ksprintf failwith "Number is in one of excluded ranges"
    | Range_float (i, j) ->
        if (not (value_not_in_ranges ranges i) ||
            not (value_not_in_ranges ranges j)) then
              Printf.ksprintf failwith "Range is in one of excluded ranges"

let check_not_values opts m =
  let excluded_values = List.map (number_of_string opts) opts.not_values in
  if excluded_values = [] then () else
  match m with
  | Range_float _ -> Printf.ksprintf failwith "--not-value cannot be used with ranges"
  | Number_float num ->
    begin
      let res = List.find_opt ((=) num) excluded_values in
      match res with
      | None -> ()
      | Some _ -> Printf.ksprintf failwith "Value is excluded by --not-value"
    end

let check_argument_type opts m =
  match m with
  | Number_float _ ->
    if opts.require_range then Printf.ksprintf failwith "Value must be a range, not a number"
    else ()
  | Range_float _ ->
    if opts.allow_range then ()
    else Printf.ksprintf failwith "Value must be a number, not a range"

let is_range_val s =
  try let _ = Pcre2.exec ~pat:"^[0-9]+-[0-9]+$" s in true
  with Not_found -> false

let var_numeric_str s =
  match is_range_val s with
  | true -> Range_string s
  | false ->  Number_string s

let () = try
  let s = var_numeric_str !number_arg in
  let opts = !opts in
  let s = get_relative opts s in
  let n =
    match s with
    | Number_string r -> Number_float (number_of_string opts r)
    | Range_string r -> let i, j = range_of_string opts r in
                   Range_float (i, j)
  in
  check_argument_type opts n;
  check_nonnegative opts n;
  check_positive opts n;
  check_not_values opts n;
  check_ranges opts n;
  check_not_ranges opts n
with (Failure err) ->
  print_endline err;
  exit 1

