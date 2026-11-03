"""Bounded, payload-free RPC timing for live appliance acceptance actors."""
import time

from control_session import ControlSession


class ObservedOwner(ControlSession):
    def __init__(self, *args, trace, **kwargs):
        self.trace = trace
        super().__init__(*args, **kwargs)

    def _rpc(self, request, **kwargs):
        started = time.monotonic()
        entry = dict(operation=request['operation'], started=started)
        if request['operation'] == 'control.dispatch':
            entry['dispatchOperation'] = request['request']['operation']
        try:
            result = super()._rpc(request, **kwargs)
            if isinstance(result, dict) and result.get('state'):
                entry.update(state=result['state'], terminalReason=result.get('terminalReason'),
                             leaseRemainingSeconds=result.get('leaseRemainingSeconds'))
            return result
        except BaseException as error:
            entry['errorCode'] = getattr(error, 'code', type(error).__name__)
            raise
        finally:
            entry['elapsedMs'] = round((time.monotonic()-started)*1000, 2)
            self.trace.append(entry)
