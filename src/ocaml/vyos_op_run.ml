(*
 * vyos-op-run: the wrapper for executing operational mode commands.
 *
 * Copyright VyOS maintainers and contributors <maintainers@vyos.io>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 or later as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *)

(* Global constants *)
let op_def_file = "/usr/share/vyos/op_cache.json"
let permissions_file = "/etc/vyos/operators.json"
let vyos_admin_group_name = "vyattacfg"

(* List of commands that operators are unconditionally denied to execute. *)
let admin_only_commands = [
  (* Configuration mode operations *)
  ["configure"];
  ["commit"];
  ["commit-confirm"];
  ["confirm"];
  (* XXX: executing a shell through a wrapper that does setuid 0
     provides a ready shell escape and defeats the purpose.
     We cannot allow operator-level users to execute shells
     in VRFs and network namespaces
     at least until we find a way to drop privileges
     after attaching to the VRF/netns but before executing the commands.
   *)
  ["execute"; "shell"];
]

(* Execution options *)
type options = {
  (* The option not to actually run the command, just print it *)
  dry_run: bool;

  (* Enable debug output *)
  debug: bool;

  (* The original VyOS command,
     like "show interfaces ethernet",
     for debugging and for substitutions of $@/$*
   *)
  vyos_command: string;
}

let default_options = {
  dry_run = false;
  debug = false;
  vyos_command = "<VyOS command is undefined>";
}

(* Exceptions and helpers *)
exception Invalid_command of string
let invalid_command msg = raise (Invalid_command msg)

exception Internal_error of string
let internal_error msg = raise (Internal_error msg)

exception Command_error of string
let command_error msg = raise (Command_error msg)

exception Permission_error
let permission_error () = raise Permission_error

exception Incomplete_command

(* Logging setup routines *)
let get_color_style () =
  let no_color = Sys.getenv_opt "NO_COLOR" |> Option.is_some in
  (* Logs always go to stderr, so we don't check if stdout is a TTY. *)
  let interactive = Unix.isatty (Unix.descr_of_out_channel stderr) in
  if interactive && (not no_color) then `Ansi_tty else `None 

let setup_logging debug =
  let level =
    if debug then Logs.Debug
    else Logs.Warning
  in
  let style = get_color_style () in
  Logs.set_level (Some level);
  Fmt_tty.setup_std_outputs ~style_renderer:style ();
  Logs.set_reporter @@ Logs.format_reporter ();
  (* Enable exception tracing if debug=true,
     by default it's disabled in the OCaml runtime *)
  if debug then Printexc.record_backtrace true

(* JSON data helpers *)
let get_string_field name obj =
  let open Yojson.Safe.Util in
  member name obj |> to_string

let read_command_definitions () =
  let () = Logs.debug @@ fun m -> m "Reading command definitions from %s" op_def_file in
  let ic = open_in op_def_file in
  let data = Yojson.Safe.from_channel ic in
  let () = close_in ic in
  data

let read_permissions () =
  let () = Logs.debug @@ fun m -> m "Reading user permissions from %s" permissions_file in
  let ic = open_in permissions_file in
  let data = Yojson.Safe.from_channel ic in
  let () = close_in ic in
  data

let find_child_node op_node word =
  let open Yojson.Safe.Util in
  let res = member word op_node in
  match res with
  | (`Assoc _) as d -> Some d
  | `Null -> None
  | _ ->
    Printf.ksprintf internal_error {|Child node "%s" is not an object!|} word

let get_node_data op_node =
  let open Yojson.Safe.Util in
  let res = member "__node_data" op_node in
  match res with
  | (`Assoc _) as d -> d
  | `Null ->
    Printf.ksprintf internal_error "Op node has no data!\n"
  | _ ->
    Printf.ksprintf internal_error "Op node data is not an object!"

let get_path node_data =
  let open Yojson.Safe.Util in
  member "path" node_data |> convert_each to_string

let get_node_type node_data =
  let open Yojson.Safe.Util in
  let res = member "node_type" node_data in
  match res with
  | `String _type -> _type
  | `Null ->
    Printf.ksprintf internal_error "Op node has no type!"
  | _ ->
    Printf.ksprintf internal_error "Op node data is not a string!"

let get_command_opt ?(field_name="command") node_data =
  let open Yojson.Safe.Util in
  let res = member field_name node_data in
  match res with
  | `String cmd -> Some cmd
  | `Null -> None
  | _ -> Printf.ksprintf internal_error "command must be a string"

let get_command ?(field_name="command") node_data =
  let res = get_command_opt ~field_name:field_name node_data in
  match res with
  | Some cmd -> cmd
  | None -> Printf.ksprintf internal_error "node is expected to have a command"

let get_virtual_tag_node node =
  let open Yojson.Safe.Util in
  let res = member "__virtual_tag" node in
  match res with
  | `Null -> None
  | _ -> Some res

(* Command permission checks *)

let rec permission_matches perm cmd =
  match perm, cmd with
  | [], _ ->
    (* If all terms of the permission matched
       all words of the command, the command is allowed --
       we follow the implicit approach
       "every permission includes all sub-commands"
     *)
    true
  | _, [] ->
    (* If the command is shorter than the permission spec,
       it means the permission is more specific.
       E.g., 'show interfaces ethernet' permission
       should reject attempts to run 'show interfaces',
       since its intent is to allow access only to Ethernet. *)
    false
  | (p :: ps), (c :: cs) ->
    (* Permission term can be either a command word
       or a special token '*' that matches any command. *)
    if (p = c) || (p = "*") then permission_matches ps cs
    else false

let group_perms_match perms group cmd =
  let get_group_perms perms g =
    let perms = Yojson.Safe.Util.path
      ["groups"; g; "command_policy"; "allow"] perms
    in
    match perms with
    | Some v ->
      (try
        v |>
        Yojson.Safe.Util.to_list |>
        List.map (fun j -> Yojson.Safe.Util.to_list j |> List.map Yojson.Safe.Util.to_string)
      with _ ->
        Printf.ksprintf internal_error
          "Command policy for group %s is not a list of string lists" g)
    | None -> Printf.ksprintf internal_error
      "Configuration does not define command policy for group %s" g
  in
  let rec perm_list_matches ps cmd =
    match ps with
    | [] -> false
    | p :: ps ->
      if permission_matches p cmd then true
      else perm_list_matches ps cmd
  in
  let group_perms = get_group_perms perms group in
  perm_list_matches group_perms cmd

let is_admin () =
  (* If executed by root, skip all permission checks *)
  if Unix.getuid () = 0 then
    let () = Logs.debug @@ fun m -> m "The user is root, permission checks will be skipped" in
    true
  else begin
    (* Otherwise, check if the user is a VyOS admin *)
    let admin_group = Unix.getgrnam vyos_admin_group_name in
    let user_groups = Unix.getgroups () in
    match (Array.find_opt ((=) admin_group.gr_gid) user_groups) with
    | Some _ ->
      let () = Logs.debug @@ fun m -> m "The user is a VyOS admin, permission checks will be skipped" in
      true
    | None ->
      let () = Logs.debug @@ fun m -> m "The user does not have VyOS admin permissions" in
      false
  end

let has_unsafe_characters cmd =
  (* XXX: this function is highly restrictive now,
     until we are completely certain that shell escape
     cannot happen down the line inside VyOS op mode scripts.
     Alphanumeric characters, hyphens, dots, and whitespace
     should allow operator users to use most commands
     that take interface names, FQDNs, and config entities
     like IPsec peer names.
     Notable exceptions are:
       - 'show bgp regexp': regexes naturally require '$' and other
         patently shell-unsafe characters.
       - 'monitor traffic interface eth0 filter':
         PCAP filters use '!', '&&' and '||',
         although people can use 'and', 'or', 'not'
         to get around the restriction.
       - 'add system image': requires non-alphanumeric characters
         for URLs.
   *)
  let () = Logs.debug @@ fun m -> m "Checking the command for unsafe characters" in
  try
    let _ = Pcre2.exec ~pat:{|[^a-zA-Z0-9_\-\.\s]|} cmd in
    let () =
      Printf.fprintf stderr "Command [%s] contains special characters \
        that operator-level users are not allowed to use\n" cmd
    in
    true
  with Not_found -> false

let is_admin_only_command cmd =
  let rec prefix_matches prefix target =
    match prefix, target with
    | [], _ ->
      (* The target matched every word of the prefix,
         so it's a match.
       *)
      true
    | _, [] ->
      (* The target is shorter than the prefix,
         so it's not a match.
       *)
      false
    | (p :: ps), (t :: ts) ->
      if p = t then prefix_matches ps ts
      else false
  in
  let () = Logs.debug @@ fun m -> m "Checking if the command is admin-only" in
  let res = List.find_opt (fun p -> prefix_matches p cmd) admin_only_commands in
  match res with
  | None -> false
  | Some _ ->
    let () = Logs.debug @@ fun m -> m "Command is reserved for admins" in
    true

let check_command_permissions perms cmd =
  let rec aux perms groups cmd =
    match groups with
    | [] -> permission_error ()
    | g :: gs ->
      if group_perms_match perms g cmd then ()
      else aux perms gs cmd
  in
  let () = Logs.debug @@ fun m -> m "Checking if the user is allowed to execute the command" in
  (* VyOS admins can execute any commands without restrictions *)
  if is_admin () then () else
  (* Operators are not allowed to execute commands
     with potentially unsafe characters in them *)
  if has_unsafe_characters (String.concat " " cmd) then permission_error () else
  (* Some commands are unconditionally denied to operators *)
  if is_admin_only_command cmd then permission_error () else
  (* Operator level users must always be in groups
     with defined command policies
   *)
  let username = Unix.getlogin () in
  let groups = Yojson.Safe.Util.path ["users"; username] perms in
  match groups with
  | None | Some (`List []) ->
    Printf.ksprintf internal_error "User %s is not assigned to any operator group" username
  | Some gs ->
    let group_list =
      (try
        gs |>
        Yojson.Safe.Util.to_list |>
        List.map Yojson.Safe.Util.to_string
       with _ ->
         Printf.ksprintf internal_error "The groups field for user %s is not a list of strings"
           username)
    in
    aux perms group_list cmd

(* Command rendering and execution *)
let render_command opts env command_tmpl =
  let () = Logs.debug @@ fun m -> m "Command template: %s" command_tmpl in
  let command_tmpl = (Mustache.of_string command_tmpl) in
  let command = Mustache.render command_tmpl (`O env) in
  let vyos_command = opts.vyos_command in
  Pcre2.replace ~pat:{|\$[@*]|} ~templ:vyos_command command

let run_external_command opts env command_tmpl =
  let cmd = render_command opts env command_tmpl in
  if opts.dry_run then Printf.printf "%s\n%!" cmd else
  (* Get the user database entry to populate the basic environment from:
     we cannot trust an unprivileged user to supply $SHELL
     or allow them to impersonate someone else by setting custom $LOGNAME, etc.
   *)
  let user_pw_entry = Unix.getpwuid @@ Unix.getuid () in
  let make_var name value = Printf.sprintf "%s=%s" name value in
  let env = [|
    (* A knowingly safe executable lookup path.
       Since we do not use /usr/local, we do not need to include that.
       Executables in VyOS-specific directories are referred to by absolute paths
       in the operational command JSON cache,
       so we don't need to include those, either.
     *)
    make_var "PATH" "/usr/sbin:/usr/bin:/sbin:/bin";
    (* Standard UNIX variables *)
    make_var "HOME" user_pw_entry.pw_dir;
    make_var "USER" user_pw_entry.pw_name;
    make_var "LOGNAME" user_pw_entry.pw_name;
    make_var "SHELL" user_pw_entry.pw_shell;
    (* VyOS-specific variables *)
    make_var "vyos_data_dir" "/usr/share/vyos";
    make_var "vyos_validators_dir" "/usr/libexec/vyos/validators";
    make_var "vyos_completion_dir" "/usr/libexec/vyos/completion";
    make_var "vyos_libexec_dir" "/usr/libexec/vyos";
    make_var "vyos_op_scripts_dir" "/usr/libexec/vyos/op_mode";
  |]
  in
  let shell = "/bin/sh" in
  (* We use execve with an absolute path to Bourne shell rather than execvpe
     so that a user trying to do PATH=/bad/place vyos-op-run
     cannot achieve anything with that trick.
   *)
  let () = Logs.debug @@ fun m -> m "Executing Unix command: %s" cmd in
  let res = Unix.execve shell [|shell; "-c"; cmd|] env in
  match res with
  | Unix.WEXITED 0 -> ()
  | _ ->
    (* Many op mode commands return non-zero exit codes on benign errors
       such as an unconfigured subsystem,
       so we shouldn't show this to the user by default.
     *)
    Logs.debug @@ fun m -> m "Execution of command '%s' failed" cmd

(* Command lookup *)
let rec run_vyos_command opts ?(env=[]) ?(parent="") node cmd_words =
  match cmd_words with
  | w :: ws ->
    let () = Logs.debug @@ fun m -> m "Looking up node '%s'" w in
    let res = find_child_node node w in
    begin match res with
    | Some child_node ->
      (* It's a normal, fixed command word *)
      run_vyos_command opts ~env:env ~parent:w child_node ws
    | None ->
      (* It's either an argument of a tag node
         or an incorrect command word *)
      let node_data = get_node_data node in
      let node_type = get_string_field "node_type" node_data in
      let virtual_tag_node = get_virtual_tag_node node in
      match node_type, virtual_tag_node with
      | "tagNode", None ->
        (* It's a simple tag node *)
        let env = (Printf.sprintf "%s-tag_value" parent, `String w) :: env in
        begin match ws with
        | [] ->
          let command = get_command node_data in
          run_external_command opts env command
        | _ as ws ->
          run_vyos_command opts ~env:env ~parent:w node ws
        end
      | "node", Some vtn ->
        (* It's a command that can be used either by itself or with an argument. *)
        let env = (Printf.sprintf "%s-tag_value" parent, `String w) :: env in
        begin match ws with
        | [] ->
          let vtn_data = get_node_data vtn in
          let command = get_command vtn_data in
          run_external_command opts env command
        | _ ->
          (* In the case of a virtual tag node, we take the parent (for variable substitution purposes)
             from the upper level.
           *)
          run_vyos_command opts ~env:env ~parent:parent vtn ws
        end
      | "node", None | "leafNode", None ->
        let path = get_path node_data in
        Printf.ksprintf invalid_command {|"%s" is not a valid argument for command [%s]|}
          w (String.concat " " path)
      | _, _ ->
        Printf.ksprintf internal_error
          {|Node with type "%s" must not have a <virtualTagNode> child|}
          node_type
    end
  | _ ->
    let node_data = get_node_data node in
    let node_type = get_node_type node_data in
    let command =
      begin match node_type with
      | "node" | "leafNode" ->
        get_command_opt node_data
      | "tagNode" ->
        (* If it's a tag node but there's no argument,
           we need to check if that tag node has standalone behavior attached to it.
         *)
        get_command_opt ~field_name:"standalone_command" node_data
      | "virtualTagNode" ->
        None
      | _ -> Printf.ksprintf internal_error {|Invalid node type "%s"|} node_type
      end
    in
    begin match command with
    | Some command ->
      run_external_command opts env command
    | None ->
      raise Incomplete_command
    end

(* Command line argument parsing *)
let usage_msg = Printf.sprintf {|Usage: %s [OPTIONS] <command>

%s is the VyOS operational command wrapper.
It is used by the CLI and can be used
for running operational commands from scripts.

Options:
|} Sys.argv.(0) Sys.argv.(0)

let get_args () =
  let opts = ref default_options in
  let args = ref [] in
  let add_positional_arg arg =
    args := arg :: !args
  in
  let arg_spec = Arg.align [
    ("--dry-run",
     Arg.Unit (fun () -> opts := {!opts with dry_run=true}),
     "Show the command instead of executing it");
    ("--debug",
     Arg.Unit (fun () -> opts := {!opts with debug=true}),
     "Enable debug output");
  ]
  in
  let () = Arg.parse arg_spec add_positional_arg usage_msg in
  let args = List.rev !args in
  ({!opts with vyos_command=(String.concat " " args)}, args)

let () =
  let debug =
    (* For simplicity, we check for the existence
       of the VYOS_DEBUG environment variable,
       rather than for specific values.
     *)
    match Unix.getenv "VYOS_DEBUG" with
    | _ -> true
    | exception Not_found -> false
  in
  let options, args = get_args () in
  (* If debug is not enabled by the environment variable,
     take it from command line options --
     it may be enabled there.
   *)
  let () = if debug then print_endline "Debug is enabled by the env var" in
  let debug = if debug then true else options.debug in
  let () = setup_logging debug in
  let op_defs = read_command_definitions () in
  let permissions = read_permissions () in
  let () = Logs.debug @@ fun m -> m "Executing VyOS command [%s]" options.vyos_command in
  try
    check_command_permissions permissions args;
    Unix.setuid 0;
    run_vyos_command options ~env:[] ~parent:"" op_defs args
  with
  | Permission_error ->
    Printf.fprintf stderr "You do not have a permission to execute VyOS command [%s]\n"
      options.vyos_command;
    exit 1
  | Invalid_command msg ->
    Printf.fprintf stderr "Invalid command [%s]: %s\n" options.vyos_command msg;
    exit 1
  | Command_error msg ->
    Printf.fprintf stderr "%s\n" msg;
  | Incomplete_command ->
    Printf.fprintf stderr "Incomplete command: %s\n" options.vyos_command;
    exit 2
  | Sys_error msg ->
    Printf.fprintf stderr "System error: %s" msg;
    exit 255
  | Unix.Unix_error (err, func, _) ->
    Printf.fprintf stderr "Failed to execute Unix call %s: %s" func (Unix.error_message err);
    exit 255
  | Internal_error msg ->
    Printf.fprintf stderr "Internal error: %s\n" msg;
    exit 255

