#ifndef _CONFIGURATION_H
#define _CONFIGURATION_H

#include <string.h>

typedef struct {
  char *hmac_key;
  size_t keyLen;
} Configuration;

Configuration config;

int setConfig(char *key);

#endif
