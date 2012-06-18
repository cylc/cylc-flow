/*
 *  header (id, version, msgtype, flags, sequencenumber, dataLen, checksum, hmac)
 *
 *  headerFmt = '!4sHHHHiH20s'    
 * 
 *  !    - pack in big endian
 * 
 *  0 -  3   4 s - char[4]         'PYRO'
 *  4 -  5   2 H - unsigned short  protocol version (44)
 *  6 -  7   2 H - unsigned short  message type
 *  8 -  9   2 H - unsigned short  flags
 * 10 - 11   2 H - unsigned short  sequence type  
 * 12 - 15   4 i - int             len(databytes)
 * 16 - 17   2 H - unsigned int    header checksum
 * 18 - 37  20 s - char[20]        hmac of message body
 *
 *
 *  headerchecksum = msgType + co 
 */

#define _PROTOCOL_VERSION 44
#define _PYRO_HEADERSIZE  32
#define _PYRO_MAGIC      0x34E9

#define _MSG_CONNECT     1
#define _MSG_CONNECTOK   2
#define _MSG_CONNECTFAIL 3
#define _MSG_INVOKE      4
#define _MSG_RESULT      5

#define _FLAGS_EXCEPTION  0x01
#define _FLAGS_COMPRESSED 0x02
#define _FLAGS_ONEWAY     0x04
#define _FLAGS_HMAC       0x08
#define _FLAGS_BATCH      0x10

#include <string.h>
#include <inttypes.h>
#include <arpa/inet.h>

#include "sha1.h"

typedef struct {
  char     pyro_tag[4];
  uint16_t protocol_version;
  uint16_t message_type;
  uint16_t flags;
  uint16_t seq;
  uint32_t msgLen;
  uint16_t checksum;
  uint8_t  body_hmac[SHA1HashSize];
} header_t;

void pack(uint16_t msgType, uint16_t flags,  uint16_t seq, char *msg, header_t *header);

void pack(uint16_t msgType, uint16_t flags,  uint16_t seq, char *msg, header_t *header)
{
  uint16_t = msg_Len = (uint16_t) strlen(msg);

  header->pyro_tag[0] = 'P'; 
  header->pyro_tag[1] = 'Y';
  header->pyro_tag[2] = 'R'; 
  header->pyro_tag[3] = 'O'; 
  header->protocol_version = htons(_PROTOCOL_VERSION);
  header->message_type = htons(msgType);
  header->flags = htons(flags);
  header->seq = htons(seq);
  header->msgLen = htonl(msgLen);
  header->checksum = htons((unint16_t)((msgType + _PROTOCOL_VERSION + msgLen + flags + seq + _PYRO_MAGIC) & 0xffff));
  header->body_hmac = bmac;  
  return;
}
