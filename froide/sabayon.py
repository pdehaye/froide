# See https://github.com/dmathieu/sabayon
# handles Let's Encrypt validation
import os

from django.http import Http404, HttpResponse

def find_key(token):
    if token == os.environ.get("ACME_TOKEN"):
        return os.environ.get("ACME_KEY")
    for k, v in os.environ.items():  #  os.environ.iteritems() in Python 2
        if v == token and k.startswith("ACME_TOKEN_"):
            n = k.replace("ACME_TOKEN_", "")
            return os.environ.get("ACME_KEY_{}".format(n))  # os.environ.get("ACME_KEY_%s" % n) in Python 2

def acme(request, token = None):
    key = find_key(token)
    if key is None:
       raise Http404
    return HttpResponse(key)
