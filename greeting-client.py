# saved as greeting-client.py
import os
import time
import Pyro5.api

name = os.getenv('NAME')

# PYRONAME:example.greeting

while True:
    greeting_maker = Pyro5.api.Proxy("PYROMETA:example.greeting") # use name server object lookup uri shortcut
    print(greeting_maker.get_fortune(name))
    time.sleep(0.1)
