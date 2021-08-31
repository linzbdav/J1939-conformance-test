import j1939

class ControllerApplication(j1939.ControllerApplication):
    def __init__(self, db, name, device_address_preferred=None, func=None):
        super().__init__(name, device_address_preferred)
        self.callback = func

    def _process_addressclaim(self, mid, data, timestamp):
        super()._process_addressclaim(mid, data, timestamp)
        if self.callback:
            self.callback(mid.priority, mid.parameter_group_number & 0x1FF00, mid.source_address, timestamp, data)
