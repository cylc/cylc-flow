/*
 *  header (id, version, msgtype, flags, sequencenumber, dataLen, checksum, hmac)
 *
 *  headerFmt = '!4sHHHHiH20s'    
 * 
 *  ! - means to pack in big endian
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
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <unistd.h>

#include "configuration.h"
#include "hmac.h" 
#include "message.h"

// create the header for a message

char *createMsgHeader(int msgtype, char *data, int flags, int sequenceNr, char *header) 
{
  unsigned char bodyhmac[hmac_size];
  int headerchecksum;
	size_t dataLen = strlen(data);
	
  if (data == NULL)
    *data = '\0';
  
  if (config.hmac_key != NULL) 
    {
      flags |= _FLAGS_HMAC;
      hmac_sha1(config.hmac_key, config.keyLen, data, dataLen, bodyhmac);
    } 
  else 
    {
      memset(bodyhmac, '\0', hmac_size);  // SHA1 digest size is 20 bytes
    }
  
  if (sequenceNr > 0xffff) 
    {
      fprintf(stderr, "sequenceNr must be 0-65535 (unsigned short)\n");
      exit(1);
    }
	
  headerchecksum = msgtype + PROTOCOL_VERSION + dataLen + flags + sequenceNr + PYRO_MAGIC;
	
  header[ 0] = 'P';
  header[ 1] = 'Y';
  header[ 2] = 'R';
  header[ 3] = 'O';
  header[ 4] = (unsigned char) (PROTOCOL_VERSION >> 8);
  header[ 5] = (unsigned char) (PROTOCOL_VERSION & 0xff);
  header[ 6] = (unsigned char) (msgtype >> 8);
  header[ 7] = (unsigned char) (msgtype & 0xff);
  header[ 8] = (unsigned char) (flags >> 8);
  header[ 9] = (unsigned char) (flags & 0xff);
  header[10] = (unsigned char) (sequenceNr >> 8);
  header[11] = (unsigned char) (sequenceNr & 0xff);
  header[12] = (unsigned char) ((dataLen >> 24) & 0xff);
  header[13] = (unsigned char) ((dataLen >> 16) & 0xff);
  header[14] = (unsigned char) ((dataLen >>  8) & 0xff);
  header[15] = (unsigned char) ( dataLen        & 0xff);
  header[16] = (unsigned char) (headerchecksum >> 8);
  header[17] = (unsigned char) (headerchecksum & 0xff);

  memcpy(header+18, bodyhmac, hmac_size);    	// 18, ..., 37 = hmac (20 bytes)

  return (header);
}

Message getMessage(int sockfd, int requiredMsgType) 
{
  unsigned char headerdata[HEADER_SIZE];
  MessageHeader header;
  unsigned char data[256];
	unsigned char bodyhmac[hmac_size];
  Message msg;
  size_t dataLen;

  read(sockfd, headerdata, HEADER_SIZE); 
  header = parseMessageHeader(headerdata);
	
  if (requiredMsgType != 0 && header.type != requiredMsgType) 
    {
      fprintf(stderr,"invalid msg type received: %d\n", header.type);
			exit(1);
		}
  dataLen = read(sockfd, data, 256);
  if (((header.flags & _FLAGS_HMAC) != 0) && (config.hmac_key != NULL)) 
    {
			hmac_sha1(config.hmac_key, config.keyLen, data, dataLen, bodyhmac);
      if (! memcmp(header.hmac, bodyhmac, hmac_size)) 
				{
					fprintf(stderr, "message hmac mismatch\n");
					exit(1);
				}
    } 
  else if (((header.flags & _FLAGS_HMAC) != 0) != (config.hmac_key != NULL)) 
    {
      fprintf(stderr, "hmac key config not symmetric\n");
			exit(1);
    }
  
  msg.type     = header.type;
  msg.flags    = header.flags;
  msg.sequence = header.sequence;
  memcpy(msg.data, data, hmac_size);

  return msg;
}

MessageHeader parseMessageHeader(unsigned char *headerdata) 
{
  MessageHeader header;
	int currentchecksum, headerchecksum;

  if (headerdata == NULL || strlen((char *) headerdata) != HEADER_SIZE) 
    {
      fprintf(stderr, "msg header data size mismatch\n");
			exit(1);
    }
  
  int version = (headerdata[4] << 8) | headerdata[5];
  if (headerdata[0]!='P' || headerdata[1]!='Y' || 
      headerdata[2]!='R' || headerdata[3]!='O' ||
      version != PROTOCOL_VERSION) 
    {
      fprintf(stderr, "invalid msg or unsupported protocol version\n");    		
			exit(1);
    }
  
  header.type = headerdata[6] & 0xff;
  header.type <<= 8;
  header.type |= headerdata[7] & 0xff;
  header.flags = headerdata[8] & 0xff;
  header.flags <<= 8;
  header.flags |= headerdata[9] & 0xff;
  header.sequence = headerdata[10] & 0xff;
  header.sequence <<= 8;
  header.sequence |= headerdata[11] & 0xff;
  header.datasize = headerdata[12] & 0xff;
  header.datasize <<= 8;
  header.datasize |= headerdata[13] & 0xff;
  header.datasize <<= 8;
  header.datasize |= headerdata[14] & 0xff;
  header.datasize <<= 8;
  header.datasize |= headerdata[15] & 0xff;

  currentchecksum = (header.type+version+header.datasize+header.flags+header.sequence+PYRO_MAGIC) & 0xffff;
  headerchecksum = headerdata[16] & 0xff;
  headerchecksum <<= 8;
  headerchecksum |= headerdata[17] & 0xff;
  if (currentchecksum != headerchecksum) 
    {
      fprintf(stderr, "msg header checksum mismatch\n");
			exit(1);
    }

  memcpy(header.hmac, headerdata+18, hmac_size);

  return header;
}



