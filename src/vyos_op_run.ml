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
  let ic = open_in op_def_file in
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

(* Command rendering and execution *)
let render_command opts env command_tmpl =
  let () = Logs.debug @@ fun m -> m "Command template: %s" command_tmpl in
  let command_tmpl = (Mustache.of_string command_tmpl) in
  let command = Mustache.render command_tmpl (`O env) in
  let vyos_command = opts.vyos_command in
  Pcre2.replace ~pat:{|\$[@*]|} ~templ:vyos_command command

let run_command opts env command_tmpl =
  let cmd = render_command opts env command_tmpl in
  if opts.dry_run then Printf.printf "%s\n%!" cmd else
  let () = Logs.debug @@ fun m -> m "Command to be executed %s" cmd in
  let res = Unix.system cmd in
  match res with
  | Unix.WEXITED 0 -> ()
  | _ -> Printf.ksprintf command_error "Execution of command '%s' failed" cmd

(* Command lookup *)
let rec find_command opts ?(env=[]) ?(parent="") node cmd_words =
  match cmd_words with
  | w :: ws ->
    let () = Logs.debug @@ fun m -> m "Looking up node '%s'" w in
    let res = find_child_node node w in
    begin match res with
    | Some child_node ->
      (* It's a normal, fixed command word *)
      find_command opts ~env:env ~parent:w child_node ws
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
          run_command opts env command
        | _ as ws ->
          find_command opts ~env:env ~parent:w node ws
        end
      | "node", Some vtn ->
        (* It's a command that can be used either by itself or with an argument. *)
        let env = (Printf.sprintf "%s-tag_value" parent, `String w) :: env in
        begin match ws with
        | [] ->
          let vtn_data = get_node_data vtn in
          let command = get_command vtn_data in
          run_command opts env command
        | _ ->
          (* In the case of a virtual tag node, we take the parent (for variable substitution purposes)
             from the upper level.
           *)
          find_command opts ~env:env ~parent:parent vtn ws
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
      run_command opts env command
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
  let () = Unix.setuid 0 in
  try
    find_command options ~env:[] ~parent:"" op_defs args
  with 
  | Invalid_command msg ->
    Printf.fprintf stderr "Invalid command [%s]: %s" options.vyos_command msg;
    exit 1
  | Command_error msg ->
    Printf.fprintf stderr "%s" msg;
  | Incomplete_command ->
    Printf.fprintf stderr "Incomplete command: %s" options.vyos_command;
    exit 2
  | Internal_error msg ->
    Printf.fprintf stderr "Internal error: %s" msg;
    exit 255

