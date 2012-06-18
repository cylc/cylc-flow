#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <netdb.h>

#include <netinet/in.h>

#include <sys/types.h>
#include <sys/socket.h>

#include <arpa/inet.h>

int retrive_grid_file(char *hostname, char *filename)
{
  struct hostent *host;
  struct sockaddr_in ServAddr;

  unsigned short ServPort;

  int i;

  const int BUFSIZE = 16384;
  char buffer[BUFSIZE];

  int sockfd;
  FILE *filefd;

  int getlen;
  char *get, *output;

  if ((output = strrchr(hostname, ':')) == NULL)
    {
      ServPort = (unsigned short) 80;
    }
  else
    {
      output = '\0';
      output++;
      ServPort = (unsigned short) atoi(output);
    }

  if ((host = gethostbyname(hostname)) == NULL)
    {
      perror("gethostbyname() failed");
      return(1);
    }

  if ((sockfd = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP)) < 0)
    {
      perror("socket() failed");
      return(1);
    }

  memset(&ServAddr, 0, sizeof(ServAddr));

  ServAddr.sin_family      = AF_INET;
  ServAddr.sin_addr.s_addr = inet_addr(inet_ntoa(*(struct in_addr *) (host->h_addr_list[0])));
  ServAddr.sin_port        = htons(ServPort);

  if (connect(sockfd, (struct sockaddr *) &ServAddr, sizeof(ServAddr)) < 0)
    {
      perror("connect() failed");
      return(1);
    }
  
  getlen = 4 + strlen(filename) + 5;
  get = (char *) malloc(sizeof(char)*(getlen+1));

  strcpy(get, "GET ");
  strcat(get, filename);
  strcat(get, " \r\n");

  printf("%s\n", get);

  write(sockfd, get, getlen);

  if ((output = strrchr(filename, '/')) == NULL)
    {
      output = get;
    }
  else
    {
      output++;
    }

  if ((filefd = fopen(output, "w")) == NULL) 
    { 
      perror("fopen failed");
      exit(1);
    } 
  
  while ((i = read(sockfd, buffer, BUFSIZE)) > 0)
    {
      printf(".");
      fwrite(buffer, sizeof(char), i, filefd);
    }
  printf("\n");
  
  close(sockfd);
  
  fclose (filefd);
  
  return 0;
}

int main(int argc, char *argv[])
{
  (void) retrive_grid_file("www.mpimet.mpg.de", "/fileadmin/software/cdo/cdo-1.3.2.tar.gz");

  return 0;
}
