open Ctypes
open Foreign

open Vyos1x
open Vyconfd_config
open Commitd_client

module VT = Vytree
module CT = Config_tree
module CD = Config_diff
module RT = Reference_tree
module TA = Tree_alg
module CM = Commit
module VC = Vycall_client

module I = Internal.Make(Config_tree)
module IR = Internal.Make(Reference_tree)

let error_message = ref ""

let make_syntax_error pos err =
  match pos with
  | None -> Printf.sprintf "Syntax error: %s" err
  | Some (l, c) ->
    Printf.sprintf "Syntax error on line %d, character %d: %s" l c err

let to_json_str = fun s -> `String s

let split_on_whitespace s = Re.split (Re.Perl.compile_pat "\\s+") s

let make_config_tree name = Ctypes.Root.create (CT.make name)

let destroy c_ptr = 
    Root.release c_ptr

let equal c_ptr_l c_ptr_r =
    (Root.get c_ptr_l) = (Root.get c_ptr_r)

let from_string s = 
  (* alert exn Parser.from_string:
      [Vyos1x.Parser.from_string] caught
   *)
  try
    error_message := "";
    let config = (Parser.from_string[@alert "-exn"]) s in
    Ctypes.Root.create config
  with
    | Failure s -> error_message := s; Ctypes.null
    | Util.Syntax_error (pos, err) ->
      let msg = make_syntax_error pos err in
      error_message := msg; Ctypes.null
    | _ -> error_message := "Parse error"; Ctypes.null

let get_error () = !error_message

let render_config c_ptr ord_val =
    CT.render_config ~ord_val:ord_val (Root.get c_ptr)

let render_json c_ptr =
    CT.render_json (Root.get c_ptr)

let render_json_ast c_ptr =
    CT.render_json_ast (Root.get c_ptr)

let render_commands c_ptr op =
    (* alert exn CT.render_commands:
        [Vytree.Nonexistent_path] not possible for path []
     *)
    match op with
    | "delete" ->
            (CT.render_commands[@alert "-exn"]) ~op:CT.Delete (Root.get c_ptr) []
    | _ ->
            (CT.render_commands[@alert "-exn"]) ~op:CT.Set (Root.get c_ptr) []

let read_internal file =
    (* alert exn Internal.read_internal:
        [Internal.Read_error] caught
     *)
    try
        error_message := "";
        let ct = (I.read_internal[@alert "-exn"]) file in
        Ctypes.Root.create ct
    with Internal.Read_error msg ->
        error_message := msg; Ctypes.null

let write_internal c_ptr file =
    (* alert exn Internal.write_internal:
        [Internal.Write_error] caught
     *)
    try
        error_message := "";
        let ct = Root.get c_ptr in
        (I.write_internal[@alert "-exn"]) ct file
    with Internal.Write_error msg ->
        error_message := msg

let create_node c_ptr path =
    (* alert exn CT.create_node:
        [Vytree.Empty_path] caught
        [Config_tree.Useless_set] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.create_node[@alert "-exn"]) ct path in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Path is empty"; 1
    (* be lenient on redundant set *)
    | CT.Useless_set -> 0

let set_add_value c_ptr path value =
    (* alert exn CT.set:
        [Vytree.Empty_path] caught
        [Config_tree.Useless_set] not reachable
        [Config_tree.Duplicate_value] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.set[@alert "-exn"]) ct path (Some value) CT.AddValue in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Path is empty"; 1
    (* be lenient on redundant value *)
    | CT.Duplicate_value -> 0

let set_replace_value c_ptr path value =
    (* alert exn CT.set:
        [Vytree.Empty_path] caught
        [Config_tree.Useless_set] not reachable
        [Config_tree.Duplicate_value] not reachable
     *)
    let	ct = Root.get c_ptr in
    let	path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.set[@alert "-exn"]) ct path (Some value) CT.ReplaceValue in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Path is empty"; 1

let set_valueless c_ptr path =
    (* alert exn CT.set:
        [Vytree.Empty_path] caught
        [Config_tree.Useless_set] caught
        [Config_tree.Duplicate_value] not reachable
     *)
    let	ct = Root.get c_ptr in
    let	path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.set[@alert "-exn"]) ct path None CT.AddValue in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Path is empty"; 1
    (* be lenient on redundant set *)
    | CT.Useless_set -> 0

let delete_value c_ptr path value =
    (* alert exn CT.delete:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
        [Config_tree.No_such_value] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.delete[@alert "-exn"]) ct path (Some value) in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Empty path"; 1
    | VT.Nonexistent_path -> error_message := "Path doesn't exist"; 1
    | CT.No_such_value -> error_message := "Value doesn't exist"; 1

let delete_node c_ptr path =
    (* alert exn CT.delete:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
        [Config_tree.No_such_value] not possible for None value
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (CT.delete[@alert "-exn"]) ct path None in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Empty path"; 1
    | VT.Nonexistent_path -> error_message := "Path doesn't exist"; 1

let rename_node c_ptr path newname =
    (* alert exn VT.rename:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
        [Not_found] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        let new_ct = (VT.rename[@alert "-exn"]) ct path newname in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Empty path"; 1
    | VT.Nonexistent_path -> error_message := "Path doesn't exist"; 1
    (* strictly speaking, the exception above will obscure the one below *)
    | Not_found -> error_message := "Path not found"; 1

let set_tag c_ptr path value =
    (* alert exn CT.set_tag:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        Root.set c_ptr ((CT.set_tag[@alert "-exn"]) ct path value);
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Empty path"; 1
    | VT.Nonexistent_path -> error_message := "Path doesn't exist"; 1

let is_tag c_ptr path =
    (* alert exn CT.set_tag:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        if ((CT.is_tag[@alert "-exn"]) ct path) then 1 else 0
    with
    | VT.Empty_path -> 0
    | VT.Nonexistent_path -> 0

let set_leaf c_ptr path value =
    (* alert exn CT.set_leaf:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        error_message := "";
        Root.set c_ptr ((CT.set_leaf[@alert "-exn"]) ct path value);
        0 (* return 0 *)
    with
    | VT.Empty_path -> error_message := "Empty path"; 1
    | VT.Nonexistent_path -> error_message := "Path doesn't exist"; 1

let is_leaf c_ptr path =
    (* alert exn CT.is_leaf:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        if ((CT.is_leaf[@alert "-exn"]) ct path) then 1 else 0
    with
    | VT.Empty_path -> 0
    | VT.Nonexistent_path -> 0

let get_subtree c_ptr path with_node =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    let subt = CT.get_subtree ~with_node:with_node ct path in
    Ctypes.Root.create subt

let exists c_ptr path =
    (* alert exn VT.exists:
        [Vytree.Empty_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        if ((VT.exists[@alert "-exn"]) ct path) then 1 else 0
    with VT.Empty_path -> 0

let value_exists c_ptr path value =
    (* alert exn VT.exists:
        [Vytree.Empty_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        if ((CT.value_exists[@alert "-exn"]) ct path value) then 1 else 0
    with VT.Empty_path -> 0

let list_nodes c_ptr path =
    (* alert exn VT.children_of_node:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        let nodes = (VT.children_of_path[@alert "-exn"]) ct path in
        let nodes_json = `List (List.map to_json_str nodes) in
        Yojson.Safe.to_string nodes_json
    with _ -> Yojson.Safe.to_string `Null

let return_value c_ptr path =
    (* alert exn CT.get_value:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
        [Config_tree.Node_has_no_value] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        Yojson.Safe.to_string (`String ((CT.get_value[@alert "-exn"]) ct path))
    with
    | CT.Node_has_no_value ->  Yojson.Safe.to_string (`String "")
    | _ -> Yojson.Safe.to_string `Null

let return_values c_ptr path =
    (* alert exn CT.get_values:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
     *)
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    let to_json_str = fun s -> `String s in
    try
        let values = (CT.get_values[@alert "-exn"]) ct path in
        let values_json = `List (List.map to_json_str values) in
        Yojson.Safe.to_string values_json
    with _ -> Yojson.Safe.to_string `Null

let copy_node c_ptr old_path new_path =
    (* alert exn VT.copy:
        [Vytree.Empty_path] caught
        [Vytree.Nonexistent_path] caught
        [Vytree.Insert_error] caught
     *)
    let ct = Root.get c_ptr in
    let old_path_str = old_path in
    let old_path = split_on_whitespace old_path in
    let new_path = split_on_whitespace new_path in
    try
        error_message := "";
        let new_ct = (VT.copy[@alert "-exn"]) ct old_path new_path in
        Root.set c_ptr new_ct;
        0
    with
    | Vytree.Empty_path ->
        error_message := "Empty path"; 1
    | Vytree.Nonexistent_path ->
        let s = Printf.sprintf "Non-existent path \'%s\'" old_path_str in
        error_message := s; 1
    | Vytree.Insert_error s -> error_message := s; 1

let diff_tree path c_ptr_l c_ptr_r =
    (* alert exn CD.diff_tree:
        [Config_diff.Incommensurable] caught
        [Config_diff.Empty_comparison] caught
     *)
    let path = split_on_whitespace path in
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = (CD.diff_tree[@alert "-exn"]) path ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; Ctypes.null
        | CD.Empty_comparison -> error_message := "Empty comparison"; Ctypes.null

let show_diff cmds path c_ptr_l c_ptr_r =
    (* alert exn CD.show_diff:
        [Config_diff.Incommensurable] caught
        [Config_diff.Empty_comparison] caught
     *)
    let path = split_on_whitespace path in
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        (CD.show_diff[@alert "-exn"]) ~cmds:cmds path ct_l ct_r
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; "#1@"
        | CD.Empty_comparison -> error_message := "Empty comparison"; "#1@"

let tree_union c_ptr_l c_ptr_r =
    (* alert exn CD.tree_union:
        [Tree_alg.Incompatible_union] caught
        [Tree_alg.Nonexistent_child] caught
     *)
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = (CD.tree_union[@alert "-exn"]) ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | TA.Nonexistent_child -> error_message := "Nonexistent child"; Ctypes.null
        | TA.Incompatible_union -> error_message := "Trees must have equivalent root"; Ctypes.null

let tree_merge destructive c_ptr_l c_ptr_r =
    (* alert exn CD.tree_merge:
        [Tree_alg.Incompatible_union] caught
        [Tree_alg.Nonexistent_child] caught
     *)
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = (CD.tree_merge[@alert "-exn"]) ~destructive:destructive ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | TA.Nonexistent_child -> error_message := "Nonexistent child"; Ctypes.null
        | TA.Incompatible_union -> error_message := "Trees must have equivalent root"; Ctypes.null

let reference_tree_to_json internal_cache from_dir to_file =
    (* alert exn Generate.reference_tree_to_json:
        [Generate.Load_error] caught
        [Generate.Write_error] caught
     *)
    try
        (Generate.reference_tree_to_json[@alert "-exn"]) ~internal_cache:internal_cache from_dir to_file;
        0
    with
        | Generate.Load_error msg ->
            let s = Printf.sprintf "Load_error \'%s\'" msg in
            error_message := s; 1
        | Generate.Write_error msg ->
            let s = Printf.sprintf "Write_error \'%s\'" msg in
            error_message := s; 1

let mask_tree c_ptr_l c_ptr_r =
    (* alert exn CD.mask_tree:
        [Config_diff.Incommensurable] caught
        [Config_diff.Empty_comparison] caught
     *)
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = (CD.mask_tree[@alert "-exn"]) ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; Ctypes.null
        | CD.Empty_comparison -> error_message := "Empty comparison"; Ctypes.null

let validate_tree_filter c_ptr rt_cache_path validator_dir =
    (* alert exn Internal.read_internal:
        [Internal.Read_error] caught
     *)
    let ct = Root.get c_ptr in
    try
        let rt = (IR.read_internal[@alert "-exn"]) rt_cache_path
        in
        let ct_ret, out =
            RT.validate_tree_filter validator_dir rt ct
        in
        error_message := out; Ctypes.Root.create ct_ret
    with Internal.Read_error msg ->
        error_message := msg; c_ptr


module Stubs(I : Cstubs_inverted.INTERNAL) =
struct

  let () = I.internal "make" (string @-> returning (ptr void)) make_config_tree
  let () = I.internal "destroy" ((ptr void) @-> returning void) destroy
  let () = I.internal "equal" ((ptr void) @-> (ptr void) @-> returning bool) equal
  let () = I.internal "from_string" (string @-> returning (ptr void)) from_string
  let () = I.internal "get_error" (void @-> returning string) get_error
  let () = I.internal "to_string"  ((ptr void) @-> bool @-> returning string) render_config
  let () = I.internal "to_json" ((ptr void) @-> returning string) render_json
  let () = I.internal "to_json_ast" ((ptr void) @-> returning string) render_json_ast
  let () = I.internal "to_commands" ((ptr void) @-> string @-> returning string) render_commands
  let () = I.internal "read_internal" (string @-> returning (ptr void)) read_internal
  let () = I.internal "write_internal" ((ptr void) @-> string @-> returning void) write_internal
  let () = I.internal "create_node" ((ptr void) @-> string @-> returning int) create_node
  let () = I.internal "set_add_value" ((ptr void) @-> string @-> string @-> returning int) set_add_value
  let () = I.internal "set_replace_value" ((ptr void) @-> string @-> string @-> returning int) set_replace_value
  let () = I.internal "set_valueless" ((ptr void) @-> string @-> returning int) set_valueless
  let () = I.internal "delete_value" ((ptr void) @-> string @-> string @-> returning int) delete_value
  let () = I.internal "delete_node" ((ptr void) @-> string @-> returning int) delete_node
  let () = I.internal "rename_node" ((ptr void) @-> string @-> string @-> returning int) rename_node
  let () = I.internal "copy_node" ((ptr void) @-> string @-> string @-> returning int) copy_node
  let () = I.internal "set_tag" ((ptr void) @-> string @-> bool @-> returning int) set_tag
  let () = I.internal "is_tag"	((ptr void) @->	string @-> returning int) is_tag
  let () = I.internal "set_leaf" ((ptr void) @-> string @-> bool @-> returning int) set_leaf
  let () = I.internal "is_leaf"  ((ptr void) @-> string @-> returning int) is_leaf
  let () = I.internal "get_subtree" ((ptr void) @-> string @-> bool @-> returning (ptr void)) get_subtree
  let () = I.internal "exists"  ((ptr void) @-> string @-> returning int) exists
  let () = I.internal "value_exists"  ((ptr void) @-> string @-> string @-> returning int) value_exists
  let () = I.internal "list_nodes" ((ptr void) @-> string @-> returning string) list_nodes
  let () = I.internal "return_value" ((ptr void) @-> string @-> returning string) return_value
  let () = I.internal "return_values" ((ptr void) @-> string @-> returning string) return_values
  let () = I.internal "diff_tree" (string @-> (ptr void) @-> (ptr void) @-> returning (ptr void)) diff_tree
  let () = I.internal "show_diff" (bool @-> string @-> (ptr void) @-> (ptr void) @-> returning string) show_diff
  let () = I.internal "tree_union" ((ptr void) @-> (ptr void) @-> returning (ptr void)) tree_union
  let () = I.internal "tree_merge" (bool @-> (ptr void) @-> (ptr void) @-> returning (ptr void)) tree_merge
  let () = I.internal "reference_tree_to_json" (string @-> string @-> string @-> returning int) reference_tree_to_json
  let () = I.internal "mask_tree" ((ptr void) @-> (ptr void) @-> returning (ptr void)) mask_tree
  let () = I.internal "validate_tree_filter" ((ptr void) @-> string @-> string @-> returning (ptr void)) validate_tree_filter
end
