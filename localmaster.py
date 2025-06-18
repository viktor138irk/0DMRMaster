import logging
import time

from dmrtools import DMRMaster
from dmrtools import AllowAllPeerAuth, ListPeerAuth
from dmrtools.parrot_app import ParrotApp


class DMRMasterLocal(DMRMaster):
    def config(self):
        # Local config
        self.set_peer_auth(AllowAllPeerAuth())
        # self.set_peer_auth(ListPeerAuth({1: 'pass1', 2: ''}))
        self.register_app(ParrotApp(9990))


def main():
    master = DMRMasterLocal();
    master.setup()
    master.run()


if __name__ == '__main__':
    main()
