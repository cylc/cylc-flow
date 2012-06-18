CC     = gcc
CFLAGS = -std=c99 -Wall -pedantic

CYLC_SRCS = configuration.c message.c hmac-sha1.c sha1.c memxor.c
CYLC_OBJS = configuration.o message.o hmac-sha1.o sha1.o memxor.o

all: libcylc 

libcylc: libcylc.a

libcylc.a: $(CYLC_OBJS)

configuration.o: configuration.c configuration.h
message.o: message.c hmac.h configuration.h
hmac-sha1.o: hmac-sha1.c sha1.h hmac.h memxor.h
sha1.o: sha1.c sha1.h
memxor.o: memxor.c memxor.h

check: digest socket

digest: digest.o hmac-sha1.o sha1.o memxor.o
	$(CC) $(CFLAGS) -o digest digest.o hmac-sha1.o sha1.o memxor.o

socket: socket.o message.o hmac-sha1.o sha1.o memxor.o configuration.o
	$(CC) $(CFLAGS) -o socket socket.o message.o hmac-sha1.o sha1.o memxor.o configuration.o

socket.o: socket.c message.h

digest.o: digest.c hmac.h

clean:
	rm -f *~ *.o digest socket
