#ifndef BEAMLINE_SERVER_H
#define BEAMLINE_SERVER_H

// Server initialization and control
int server_init(void);  // Returns listen_fd
void server_run_once(int listen_fd);  // One iteration of event loop
void server_cleanup(int listen_fd);

#endif // BEAMLINE_SERVER_H
