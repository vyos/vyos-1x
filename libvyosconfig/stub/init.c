#include <caml/callback.h>

__attribute__ ((__constructor__))
void
init(void)
{
  char *caml_argv[1] = { NULL };
  caml_startup(caml_argv);
}
