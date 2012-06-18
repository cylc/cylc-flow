#include <stdlib.h>

#include "configuration.h"

int setConfig(char *key)
{
  config.keyLen = strlen(key);
  config.hmac_key = (char *) malloc((config.keyLen+1)*sizeof(char));
  memcpy(config.hmac_key, key, config.keyLen+1);

  return 0;
}
