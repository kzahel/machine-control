"""Serial metadata mailbox; discovery requests confer no control authority."""
import copy


class Updates:
    def __init__(self):
        self.state = None
        self.requested = False

    def sync(self, state):
        if not isinstance(state, dict):
            raise ValueError("Update state required")
        self.state = copy.deepcopy(state)
        requested, self.requested = self.requested, False
        if requested and not self.state.get("installing"):
            self.state.update(checking=True, phase="checking", reason="manual")
        return requested

    def request(self, check=False):
        if self.state is None:
            raise ValueError("Desktop updater is initializing")
        if check and not self.state.get("checking") and not self.state.get("installing"):
            self.requested = True
        return {"queued": self.requested, "update": copy.deepcopy(self.state)}
