#!/usr/bin/env python3

import argparse
import smtplib
import sys

parser = argparse.ArgumentParser(description='Cylc functional tests mail command.')
parser.add_argument('-s', metavar='subject', dest='subject', type=str, help='e-mail subject')
parser.add_argument('-r', metavar='reply_to', dest='sender', type=str, help='e-mail reply-to address')
parser.add_argument('to', metavar='to', type=str, help='e-mail destination address')
parser.add_argument('body', metavar='body', nargs='?', type=argparse.FileType('r'), default=sys.stdin, help='e-mail body')

args = parser.parse_args()

port = 8025
smtp_server = "localhost"
sender_email = args.sender
receiver_email = args.to
message = f"""\
Subject: {args.subject}

{args.body.read()}"""

# https://realpython.com/python-send-email/
with smtplib.SMTP(smtp_server, port) as server:
    server.sendmail(sender_email, receiver_email, message)
