#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <semaphore.h>
#include <assert.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/ip.h>

sem_t sem;

void signal_handler(int signo)
{
    sem_post(&sem);
}

#define MAX_SLEEP_PER_GROUP_US 200000
#define MAX_GROUPS 10000
#define MAX_GROUP_NAME 256

struct iteration {
    uint32_t n_groups;
    char groups[MAX_GROUPS][MAX_GROUP_NAME];
    int sd[MAX_GROUPS];
};

static void init_socket(int *sd)
{
    struct sockaddr_in addr;

    *sd = socket(AF_INET, SOCK_DGRAM, 0);
    if (*sd < 0) {
        perror("opening datagram socket");
        exit(1);
    }

    int reuse=1;

    if (setsockopt(*sd, SOL_SOCKET, SO_REUSEADDR,
                   (char *)&reuse, sizeof(reuse)) < 0) {
        perror("setting SO_REUSEADDR");
        exit(1);
    }

    memset((char *) &addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(5555);;
    addr.sin_addr.s_addr  = INADDR_ANY;

    if (bind(*sd, (struct sockaddr*)&addr, sizeof(addr))) {
        perror("binding datagram socket");
        exit(1);
    }
}

static void join_mcast_group(int sd, const char *g_name)
{
    struct ip_mreq group;

    usleep(rand() % (MAX_SLEEP_PER_GROUP_US / MAX_GROUPS));

    group.imr_multiaddr.s_addr = inet_addr(g_name);
    if (setsockopt(sd, IPPROTO_IP, IP_ADD_MEMBERSHIP,
                   (char *)&group, sizeof(group)) < 0) {
        perror("adding multicast group");
        exit(1);
    }
}

int main (int argc, char *argv[])
{
    struct iteration *iterations;
    uint32_t i;
    uint32_t j;

    sem_init(&sem, 0, 0);

    signal(SIGUSR1, signal_handler);

    FILE *f;

    assert(f = fopen(argv[1], "r"));

    uint32_t n_iterations;

    assert(fscanf(f, "%u\n", &n_iterations) == 1);
    iterations = malloc(n_iterations * sizeof(*iterations));
    assert(iterations);

    for (i = 0; i < n_iterations; i++) {
        assert(fscanf(f, "%u\n", &iterations[i].n_groups));

        for (j = 0; j < iterations[i].n_groups; j++) {
            assert(fgets(iterations[i].groups[j], MAX_GROUP_NAME, f));
            init_socket(&iterations[i].sd[j]);
        }
    }

    daemon(1, 0);

    for (i = 0; i < n_iterations; i++) {
        sem_wait(&sem);

        for (j = 0; j < iterations[i].n_groups; j++) {
            join_mcast_group(iterations[i].sd[j], iterations[i].groups[j]);
        }
    }

    for (;;) sleep(1000000);
    return 0;
}
