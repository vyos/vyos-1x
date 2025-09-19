open Ctypes
open Foreign

open Vyos1x
open Vyconfd_config
open Commitd_client

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
  try
    error_message := "";
    let config = Parser.from_string s in
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
    match op with
    | "delete" ->
            CT.render_commands ~op:CT.Delete (Root.get c_ptr) []
    | _ ->
            CT.render_commands ~op:CT.Set (Root.get c_ptr) []

let read_internal file =
    try
        error_message := "";
        let ct = I.read_internal file in
        Ctypes.Root.create ct
    with Internal.Read_error msg ->
        error_message := msg; Ctypes.null

let write_internal c_ptr file =
    try
        error_message := "";
        let ct = Root.get c_ptr in
        I.write_internal ct file
    with Internal.Write_error msg ->
        error_message := msg

let create_node c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        let new_ct = CT.create_node ct path in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with CT.Useless_set -> 1

let set_add_value c_ptr path value =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        let new_ct = CT.set ct path (Some value) CT.AddValue in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with CT.Duplicate_value -> 1

let set_replace_value c_ptr path value =
    let	ct = Root.get c_ptr in
    let	path = split_on_whitespace path in
    let new_ct = Config_tree.set ct path (Some value) Config_tree.ReplaceValue in
    Root.set c_ptr new_ct;
    0 (* return 0 *)

let set_valueless c_ptr path =
    let	ct = Root.get c_ptr in
    let	path = split_on_whitespace path in
    try
        let new_ct = Config_tree.set ct path None CT.AddValue in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with CT.Useless_set -> 1

let delete_value c_ptr path value =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        let new_ct = CT.delete ct path (Some value) in
        Root.set c_ptr new_ct;
        0 (* return 0 *)
    with
    | Vytree.Nonexistent_path -> 1
    | CT.No_such_value -> 2

let delete_node c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    if not (Vytree.exists ct path) then 1 else
    let new_ct = Config_tree.delete ct path None in
    Root.set c_ptr new_ct;
    0 (* return 0 *)

let rename_node c_ptr path newname =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    if not (Vytree.exists ct path) then 1 else
    let new_ct = Vytree.rename ct path newname in
    Root.set c_ptr new_ct;
    0 (* return 0 *)

let set_tag c_ptr path value =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        Root.set c_ptr (CT.set_tag ct path value);
        0 (* return 0 *)
    with _ -> 1

let is_tag c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    if (CT.is_tag ct path) then 1 else 0

let set_leaf c_ptr path value =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        Root.set c_ptr (CT.set_leaf ct path value);
        0 (* return 0 *)
    with _ -> 1

let is_leaf c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    CT.is_leaf ct path

let get_subtree c_ptr path with_node =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    let subt = CT.get_subtree ~with_node:with_node ct path in
    Ctypes.Root.create subt

let exists c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    if (Vytree.exists ct path) then 1 else 0

let list_nodes c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        let nodes = Vytree.children_of_path ct path in
        let nodes_json = `List (List.map to_json_str nodes) in
        Yojson.Safe.to_string nodes_json
    with _ -> Yojson.Safe.to_string `Null

let return_value c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    try
        Yojson.Safe.to_string (`String (CT.get_value ct path))
    with
    | CT.Node_has_no_value ->  Yojson.Safe.to_string (`String "")
    | _ -> Yojson.Safe.to_string `Null

let return_values c_ptr path =
    let ct = Root.get c_ptr in
    let path = split_on_whitespace path in
    let to_json_str = fun s -> `String s in
    try
       	let values = CT.get_values ct path in
        let values_json = `List (List.map to_json_str values) in
        Yojson.Safe.to_string values_json
    with _ -> Yojson.Safe.to_string `Null

let copy_node c_ptr old_path new_path =
    let ct = Root.get c_ptr in
    let old_path_str = old_path in
    let old_path = split_on_whitespace old_path in
    let new_path = split_on_whitespace new_path in
    try
        let new_ct = Vytree.copy ct old_path new_path in
        Root.set c_ptr new_ct;
        0
    with
    | Vytree.Nonexistent_path ->
        let s = Printf.sprintf "Non-existent path \'%s\'" old_path_str in
        error_message := s; 1
    | Vytree.Insert_error s -> error_message := s; 1

let diff_tree path c_ptr_l c_ptr_r =
    let path = split_on_whitespace path in
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = CD.diff_tree path ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; Ctypes.null
        | CD.Empty_comparison -> error_message := "Empty comparison"; Ctypes.null

let show_diff cmds path c_ptr_l c_ptr_r =
    let path = split_on_whitespace path in
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        CD.show_diff ~cmds:cmds path ct_l ct_r
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; "#1@"
        | CD.Empty_comparison -> error_message := "Empty comparison"; "#1@"

let tree_union c_ptr_l c_ptr_r =
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = CD.tree_union ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | TA.Nonexistent_child -> error_message := "Nonexistent child"; Ctypes.null
        | TA.Incompatible_union -> error_message := "Trees must have equivalent root"; Ctypes.null

let tree_merge destructive c_ptr_l c_ptr_r =
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = CD.tree_merge ~destructive:destructive ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | TA.Nonexistent_child -> error_message := "Nonexistent child"; Ctypes.null
        | TA.Incompatible_union -> error_message := "Trees must have equivalent root"; Ctypes.null

let reference_tree_to_json internal_cache from_dir to_file =
    try
        Generate.reference_tree_to_json ~internal_cache:internal_cache from_dir to_file; 0
    with
        | Generate.Load_error msg ->
            let s = Printf.sprintf "Load_error \'%s\'" msg in
            error_message := s; 1
        | Generate.Write_error msg ->
            let s = Printf.sprintf "Write_error \'%s\'" msg in
            error_message := s; 1

let mask_tree c_ptr_l c_ptr_r =
    let ct_l = Root.get c_ptr_l in
    let ct_r = Root.get c_ptr_r in
    try
        let ct_ret = CD.mask_tree ct_l ct_r in
        Ctypes.Root.create ct_ret
    with
        | CD.Incommensurable -> error_message := "Incommensurable"; Ctypes.null
        | CD.Empty_comparison -> error_message := "Empty comparison"; Ctypes.null

let validate_tree_filter c_ptr rt_cache_path validator_dir =
    let ct = Root.get c_ptr in
    try
        let rt = IR.read_internal rt_cache_path
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
  let () = I.internal "is_leaf"  ((ptr void) @-> string @-> returning bool) is_leaf
  let () = I.internal "get_subtree" ((ptr void) @-> string @-> bool @-> returning (ptr void)) get_subtree
  let () = I.internal "exists"  ((ptr void) @-> string @-> returning int) exists
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
