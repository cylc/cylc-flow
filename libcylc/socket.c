#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <netdb.h>

#include <netinet/in.h>

#include <sys/types.h>
#include <sys/socket.h>

#include <arpa/inet.h>

#include "configuration.h"
#include "message.h"

char request_message[] = "(S'report'\np1\nS'get_report'\np2\n(S'm214089'\np3\ntp4\n(dp5\ntp6\n."; 

int main(int argc, char *argv[])
{
  struct hostent *host;
  struct sockaddr_in ServAddr;

  unsigned short ServPort;

  int i;

  const int BUFSIZE = 16384;
  char buffer[BUFSIZE];

  int sockfd;

  setConfig("cylc"); 

	ServPort = (unsigned short) 57007;

  if ((host = gethostbyname("localhost")) == NULL)
    {
      perror("gethostbyname() failed");
      return(1);
    }

	fprintf(stderr, "... create socket\n");
  if ((sockfd = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP)) < 0)
    {
      perror("socket() failed");
      return(1);
    }
  if ((sockfd = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP)) < 0)
    {
      perror("socket() failed");
      return(1);
    }
	fprintf(stderr, "socket created ...\n");

  memset(&ServAddr, 0, sizeof(ServAddr));

  ServAddr.sin_family      = AF_INET;
  ServAddr.sin_addr.s_addr = inet_addr(inet_ntoa(*(struct in_addr *) (host->h_addr_list[0])));
  ServAddr.sin_port        = htons(ServPort);

	fprintf(stderr, "... connect server\n");
  if (connect(sockfd, (struct sockaddr *) &ServAddr, sizeof(ServAddr)) < 0)
    {
      perror("connect() failed");
      return(1);
    }
	fprintf(stderr, "server connected\n");
  
	fprintf(stderr, "... get ok record\n");  
  i = read(sockfd, buffer, BUFSIZE);
	fprintf(stderr, "got ok record with %d bytes (expect 40) ... \n", i);  

	{
		int k;

		//    MessageHeader header;
		//		header = parseMessageHeader((unsigend char *)buffer);    
  
		for (k = 0; k < HEADER_SIZE; k ++) 
			{
				fprintf(stderr, "0x%2.2x ", (unsigned char ) buffer[k]); 
				if (((k+1) % 8) == 0) fprintf(stderr, "\n");
			}
		fprintf(stderr, "\n");
		fprintf(stderr, "... message: %c%c\n", buffer[HEADER_SIZE], buffer[HEADER_SIZE+1]);

	}

	// construct message to get report ...

	{
		unsigned char request_header[HEADER_SIZE];
    int k;
		createMsgHeader(_MSG_INVOKE, request_message, _FLAGS_HMAC, 0, (char *) request_header);
		for (k = 0; k < HEADER_SIZE; k ++) 
			{
				fprintf(stderr, "0x%2.2x ", (unsigned char ) request_header[k]); 
				if (((k+1) % 8) == 0) fprintf(stderr, "\n");
			}
		fprintf(stderr, "\n");
		fprintf(stderr, "HMAC:\n");
		for (k = 0; k < 20; k ++) 
			{
				fprintf(stderr, "0x%2.2x ", (unsigned char ) request_header[18+k]); 
			}
		fprintf(stderr, "\n");
	}

  close(sockfd);

  return 0;
}
