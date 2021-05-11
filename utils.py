import base64
import email
import os
import re
import smtplib
import sys
from typing import List
from pyisemail import is_email
import dns.resolver


def check_email_accessible(email):
    try:

        from_address = 'email.checker2021@gmail.com'

        # Get domain for DNS lookup
        domain = email.split('@')[-1]

        # experimental part
        # we make a deliberately non-existent email with the required domain
        # first_part, second_part = email.split('@')
        # fake_email = first_part + 'ashdfabebdfjksjakuahfka' + '@' + second_part

        # MX record lookup
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = records[0].exchange
        mx_record = str(mx_record)

        # SMTP lib setup (use debug level for full output)
        server = smtplib.SMTP()
        server.set_debuglevel(0)

        # SMTP Conversation
        server.connect(mx_record)
        server.helo(server.local_hostname)  # server.local_hostname(Get local server hostname)
        server.mail(from_address)
        code, message = server.rcpt(email)
        print(f'email: {email}, code: {code}')
        server.quit()

        # Assume SMTP response 250 is success
        if code == 250:
            return True
        else:
            return False

    except Exception as e: # noqa
        return False
