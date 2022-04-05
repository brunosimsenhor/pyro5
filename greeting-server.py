# saved as greeting-server.py
import os
import uuid
import Pyro5.api

hostname = os.getenv("HOSTNAME")

print("Starting greeting server {0}...".format(hostname))

@Pyro5.api.expose
class GreetingMaker(object):
    def get_fortune(self, name):
        _uuid = uuid.uuid4()
        print("[{0}]".format(_uuid))

        return "Hello, {0}. Here is your fortune message:\n" \
               "Tomorrow's lucky number is {1}.".format(name, _uuid)

daemon = Pyro5.server.Daemon(host = hostname)             # make a Pyro daemon
ns = Pyro5.api.locate_ns()                                # find the name server
uri = daemon.register(GreetingMaker)                      # register the greeting maker as a Pyro object
ns.register("example.greeting.{0}".format(hostname), uri, metadata = {"example.greeting"}) # register the object with a name in the name server

print("Ready.")
daemon.requestLoop()                                      # start the event loop of the server to wait for calls
