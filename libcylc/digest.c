#include <stdio.h>
#include <string.h>

#include "hmac.h"

int main(int argc, char *argv[])
{
  char *key = "Jefe";
  size_t keyLen = 4;
  char *data = "what do ya want for nothing?";
  size_t dataLen = 28;
   
  char *reference = "\xef\xfc\xdf\x6a\xe5\xeb\x2f\xa2\xd2\x74\x16\xd5\xf1\x84\xdf\x9c\x25\x9a\x7c\x79";
  char digest[20];

  size_t i;
  
  if (hmac_sha1(key, keyLen, data, dataLen, digest) != 0)
    {
      printf ("call failure\n");
      return 1;
    }
  
  if (memcmp (reference, digest, 20) != 0)
    {
      printf ("hash 2 mismatch. expected:\n");
      for (i = 0; i < 20; i++)
	printf ("%02x ", reference[i] & 0xff);
      printf ("\ncomputed:\n");
      for (i = 0; i < 20; i++)
	printf ("%02x ", digest[i] & 0xff);
      printf ("\n");
      return 1;
    }
  else
    {
      for (i = 0; i < 20; i++)
	printf ("%02x ", digest[i] & 0xff);
      printf ("\n");
    }

  return 0;
}
