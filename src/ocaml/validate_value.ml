type argopt = RegexOpt of string | ExecOpt of string | GroupSeparator
type check = Regex of string | Exec of string | Group of check list

let options = ref []
let checks = ref []
let value = ref ""
let silent = ref false

let buf = Buffer.create 4096

let rec validate_value buf value_constraint value =
  match value_constraint with
  | Group l ->
    List.for_all (fun c -> validate_value buf c value) l
  | Regex s ->
    (try let _ = Pcre2.exec ~pat:(Printf.sprintf "^%s$" s) value in true
     with Not_found -> false)
  | Exec c ->
    (match Native_validators.dispatch c value with
     | Some (true, _) -> true
     | Some (false, msg) -> Buffer.add_string buf msg; Buffer.add_string buf "\n"; false
     | None ->
    (* XXX: Unix.open_process_in is "shelling out", which is a bad idea on multiple levels,
       especially when the input comes directly from the user...
       We should do something about it.
     *)
    let cmd = Printf.sprintf "%s \'%s\' 2>&1" c value in
    let chan = Unix.open_process_in cmd in
    let out = try CCIO.read_all chan with _ -> "" in
    let result = Unix.close_process_in chan in
    match result with
    | Unix.WEXITED 0 -> true
    | Unix.WEXITED 127 ->
      let () = Printf.printf "Could not execute validator %s" c in
      false
    | _ ->
      let () = Buffer.add_string buf out; Buffer.add_string buf "\n" in
      false)

let args = [
  ("--regex", Arg.String (fun s -> options := (RegexOpt s) :: !options), "Check the value against a regex");
  ("--exec", Arg.String (fun s -> options := (ExecOpt s) :: !options), "Check the value against an external command");
  ("--grp", Arg.Unit (fun () -> options := (GroupSeparator) :: !options), "Group following arguments, combining results with logical and");
  ("--silent", Arg.Unit (fun () -> silent := true), "Suppress individual validator output");
  ("--value", Arg.String (fun s -> value := s), "Value to check");
]
let usage = Printf.sprintf "Usage: %s [OPTIONS] <number>" Sys.argv.(0)

let () = Arg.parse args (fun _ -> ()) usage

let find_next_group n l =
  let rec aux i = function
    | [] -> List.length l
    | h::t ->
      if i > n && h = GroupSeparator then i
      else aux (i+1) t
  in aux 0 l

let get_next_range =
  let n = ref (-1) in
  let f () =
    let i = !n and j = (n := find_next_group !n !options; !n) in
    (i, j) in
  f

let option_to_check opt =
  match opt with
  | RegexOpt s -> Regex s
  | ExecOpt s -> Exec s
  | GroupSeparator -> raise (Invalid_argument "GroupSeparator in isolation has no corresponding check")

let read_initial_options j =
  if j > 0 then
    let initial_options = List.filteri (fun i _ -> i < j) !options in
    ignore (List.map (fun c -> checks := (option_to_check c) :: !checks) initial_options); ()
  else ()

let read_group_options i j =
  if i < j then
    let group_options = List.filteri (fun k _ -> i < k && k < j) !options in
    let l = List.map (fun c -> option_to_check c) group_options in
    checks := (Group l) :: !checks; ()
  else ()

let read_options () =
  options := List.rev(!options);

  let (_, j) = get_next_range () in
  read_initial_options j;

  let quit_loop = ref false in
  while not !quit_loop do
    let i, j = get_next_range () in
    if i < j then
      read_group_options i j
    else
      quit_loop := true
  done

let validate =
  read_options ();
  let value = !value in
  let checks = !checks in
  match checks with
  | [] -> false
  | _ ->
    List.exists (fun c -> validate_value buf c value) checks

let _ =
  if validate then exit 0 else
    (* If we got this far, value validation failed.
       Show the user output from the validators.
     *)
    if not !silent then Buffer.contents buf |> print_endline
    else ();
    exit 1
