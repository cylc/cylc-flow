#ifndef _MESSAGE_H
#define _MESSAGE_H

typedef struct {
  int type;
  int flags;
  int sequence;
  char *data;
} Message;

typedef struct {
  int type;
  int flags;
  int sequence;
  int datasize;
  unsigned char hmac[20];
} MessageHeader;

static const unsigned short _MSG_CONNECT      = 1;
static const unsigned short _MSG_CONNECTOK    = 2;
static const unsigned short _MSG_CONNECTFAIL  = 3;
static const unsigned short _MSG_INVOKE       = 4;
static const unsigned short _MSG_RESULT       = 5;

static const unsigned short _FLAGS_EXCEPTION  = 1 << 0;
static const unsigned short _FLAGS_COMPRESSED = 1 << 1;
static const unsigned short _FLAGS_ONEWAY     = 1 << 2;
static const unsigned short _FLAGS_HMAC       = 1 << 3;
static const unsigned short _FLAGS_BATCH      = 1 << 4;

static const unsigned short PYRO_MAGIC = 0x34e9;

static const unsigned short PROTOCOL_VERSION = 44;

static const unsigned short HEADER_SIZE = 38;

char *createMsgHeader(int msgtype, char *data, int flags, int sequenceNr, char *header); 
Message getMessage(int sockfd, int requiredMsgType); 
MessageHeader parseMessageHeader(unsigned char *headerdata); 

#endif
