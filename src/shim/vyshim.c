/*
 * Copyright (C) 2020-2024 VyOS maintainers and contributors
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
 *
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <zmq.h>
#include "mkjson.h"

/*
 *
 *
 */

#if DEBUG
#define DEBUG_ON 1
#else
#define DEBUG_ON 0
#endif
#define debug_print(fmt, ...) \
    do { if (DEBUG_ON) fprintf(stderr, fmt, ##__VA_ARGS__); } while (0)
#define debug_call(f) \
    do { if (DEBUG_ON) f; } while (0)

#define SOCKET_PATH "ipc:///run/vyos-configd.sock"

#define GET_ACTIVE "cli-shell-api --show-active-only --show-show-defaults --show-ignore-edit showConfig"
#define GET_SESSION "cli-shell-api --show-working-only --show-show-defaults --show-ignore-edit showConfig"

#define COMMIT_MARKER "/var/tmp/initial_in_commit"
#define QUEUE_MARKER "/var/tmp/last_in_queue"

enum {
    SUCCESS =      1 << 0,
    ERROR_COMMIT = 1 << 1,
    ERROR_DAEMON = 1 << 2,
    PASS =         1 << 3
};

volatile int init_alarm = 0;
volatile int timeout = 0;

int initialization(void *);
int pass_through(char **, int);
void timer_handler(int);

double get_posix_clock_time(void);

int main(int argc, char* argv[])
{
    // string for node data: conf_mode script and tagnode, if applicable
    char string_node_data[256];
    string_node_data[0] = '\0';

    void *context = zmq_ctx_new();
    void *requester = zmq_socket(context, ZMQ_REQ);

    int ex_index;
    int init_timeout = 0;
    int last = 0;

    debug_print("Connecting to vyos-configd ...\n");
    zmq_connect(requester, SOCKET_PATH);

    for (int i = 1; i < argc ; i++) {
        strncat(&string_node_data[0], argv[i], 127);
    }

    debug_print("data to send: %s\n", string_node_data);

    char *test = strstr(string_node_data, "VYOS_TAGNODE_VALUE");
    ex_index = test ? 2 : 1;

    if (access(COMMIT_MARKER, F_OK) != -1) {
        init_timeout = initialization(requester);
        if (!init_timeout) remove(COMMIT_MARKER);
    }

    // if initial communication failed, pass through execution of script
    if (init_timeout) {
        int ret = pass_through(argv, ex_index);
        return ret;
    }

    if (access(QUEUE_MARKER, F_OK) != -1) {
        last = 1;
        remove(QUEUE_MARKER);
    }

    char error_code[1];
    debug_print("Sending node data ...\n");
    char *string_node_data_msg = mkjson(MKJSON_OBJ, 3,
                                        MKJSON_STRING, "type", "node",
                                        MKJSON_BOOL, "last", last,
                                        MKJSON_STRING, "data", &string_node_data[0]);

    zmq_send(requester, string_node_data_msg, strlen(string_node_data_msg), 0);
    zmq_recv(requester, error_code, 1, 0);
    debug_print("Received node data receipt\n");

    int err = (int)error_code[0];

    free(string_node_data_msg);

    zmq_close(requester);
    zmq_ctx_destroy(context);

    if (err & PASS) {
        debug_print("Received PASS\n");
        int ret = pass_through(argv, ex_index);
        return ret;
    }

    if (err & ERROR_DAEMON) {
        debug_print("Received ERROR_DAEMON\n");
        int ret = pass_through(argv, ex_index);
        return ret;
    }

    if (err & ERROR_COMMIT) {
        debug_print("Received ERROR_COMMIT\n");
        return -1;
    }

    return 0;
}

int initialization(void* Requester)
{
    char *active_str = NULL;
    size_t active_len = 0;

    char *session_str = NULL;
    size_t session_len = 0;

    char *empty_string = "\n";

    char buffer[16];

    struct sigaction sa;
    struct itimerval timer, none_timer;

    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = &timer_handler;
    sigaction(SIGALRM, &sa, NULL);

    timer.it_value.tv_sec = 0;
    timer.it_value.tv_usec = 10000;
    timer.it_interval.tv_sec = timer.it_interval.tv_usec = 0;
    none_timer.it_value.tv_sec = none_timer.it_value.tv_usec = 0;
    none_timer.it_interval.tv_sec = none_timer.it_interval.tv_usec = 0;

    double prev_time_value, time_value;
    double time_diff;

    char *pid_val = getenv("VYATTA_CONFIG_TMP");
    strsep(&pid_val, "_");
    debug_print("config session pid: %s\n", pid_val);

    debug_print("Sending init announcement\n");
    char *init_announce = mkjson(MKJSON_OBJ, 1,
                                 MKJSON_STRING, "type", "init");

    // check for timeout on initial contact
    while (!init_alarm) {
        debug_call(prev_time_value = get_posix_clock_time());

        setitimer(ITIMER_REAL, &timer, NULL);

        zmq_send(Requester, init_announce, strlen(init_announce), 0);
        zmq_recv(Requester, buffer, 16, 0);

        setitimer(ITIMER_REAL, &none_timer, &timer);

        debug_call(time_value = get_posix_clock_time());

        debug_print("Received init receipt\n");
        debug_call(time_diff = time_value - prev_time_value);
        debug_print("time elapse %f\n", time_diff);

        break;
    }

    free(init_announce);

    if (timeout) return -1;

    FILE *fp_a = popen(GET_ACTIVE, "r");
    getdelim(&active_str, &active_len, '\0', fp_a);
    int ret = pclose(fp_a);

    if (!ret) {
        debug_print("Sending active config\n");
        zmq_send(Requester, active_str, active_len - 1, 0);
        zmq_recv(Requester, buffer, 16, 0);
        debug_print("Received active receipt\n");
    } else {
        debug_print("Sending empty active config\n");
        zmq_send(Requester, empty_string, 0, 0);
        zmq_recv(Requester, buffer, 16, 0);
        debug_print("Received active receipt\n");
    }

    free(active_str);

    FILE *fp_s = popen(GET_SESSION, "r");
    getdelim(&session_str, &session_len, '\0', fp_s);
    pclose(fp_s);

    debug_print("Sending session config\n");
    zmq_send(Requester, session_str, session_len - 1, 0);
    zmq_recv(Requester, buffer, 16, 0);
    debug_print("Received session receipt\n");

    free(session_str);

    debug_print("Sending config session pid\n");
    zmq_send(Requester, pid_val, strlen(pid_val), 0);
    zmq_recv(Requester, buffer, 16, 0);
    debug_print("Received pid receipt\n");


    return 0;
}

int pass_through(char **argv, int ex_index)
{
    char **newargv = NULL;
    pid_t child_pid;

    newargv = &argv[ex_index];
    if (ex_index > 1) {
        putenv(argv[ex_index - 1]);
    }

    debug_print("pass-through invoked\n");

    if ((child_pid=fork()) < 0) {
        debug_print("fork() failed\n");
        return -1;
    } else if (child_pid == 0) {
        if (-1 == execv(argv[ex_index], newargv)) {
            debug_print("pass_through execve failed %s: %s\n",
                        argv[ex_index], strerror(errno));
            return -1;
        }
    } else if (child_pid > 0) {
        int status;
        pid_t wait_pid = waitpid(child_pid, &status, 0);
         if (wait_pid < 0) {
             debug_print("waitpid() failed\n");
             return -1;
         } else if (wait_pid == child_pid) {
             if (WIFEXITED(status)) {
                 debug_print("child exited with code %d\n",
                             WEXITSTATUS(status));
                 return WEXITSTATUS(status);
             }
         }
    }

    return 0;
}

void timer_handler(int signum)
{
    debug_print("timer_handler invoked\n");
    timeout = 1;
    init_alarm = 1;

    return;
}

#ifdef _POSIX_MONOTONIC_CLOCK
double get_posix_clock_time(void)
{
    struct timespec ts;

    if (clock_gettime(CLOCK_MONOTONIC, &ts) == 0) {
        return (double) (ts.tv_sec + ts.tv_nsec / 1000000000.0);
    } else {
        return 0;
    }
}
#else
double get_posix_clock_time(void)
{return (double)0;}
#endif
