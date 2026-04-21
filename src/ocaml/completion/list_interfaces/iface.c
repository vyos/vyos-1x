/*
 * Simple wrapper of getifaddrs for OCaml list of interfaces
 */
#include <ifaddrs.h>
#include <caml/mlvalues.h>
#include <caml/memory.h>
#include <caml/alloc.h>

CAMLprim value interface_list(value unit) {
    struct ifaddrs *ifaddr;
    struct ifaddrs *ifa;

    CAMLparam1( unit );
    CAMLlocal2( cli, cons );

    cli = Val_emptylist;

    if (getifaddrs(&ifaddr) == -1) {
        CAMLreturn(cli);
    }
    for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
        if (ifa->ifa_name == NULL)
            continue;

        CAMLlocal1( ml_s );
        cons = caml_alloc(2, 0);

        ml_s = caml_copy_string(ifa->ifa_name);
        Store_field( cons, 0, ml_s );
        Store_field( cons, 1, cli );

        cli = cons;
    }

    freeifaddrs(ifaddr);

    CAMLreturn(cli);
}
