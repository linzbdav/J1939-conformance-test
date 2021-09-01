import j1939
import canmatrix

class Name(j1939.Name):
    ATTR_MAP = {
        'arbitrary_address_capable': 'NmJ1939AAC',
        'industry_group':'NmJ1939IndustryGroup',
        'vehicle_system_instance':'NmJ1939SystemInstance',
        'vehicle_system':'NmJ1939System',
        'function':'NmJ1939Function',
        'function_instance':'NmJ1939FunctionInstance',
        'ecu_instance':'NmJ1939ECUInstance',
        'manufacturer_code':'NmJ1939ManufacturerCode',
        'identity_number':'NmJ1939IdentityNumber'
    }

    def __init__(self, ecu):
        identity_number = ecu.attribute(self.ATTR_MAP['identity_number'])
        if identity_number:
            identity_number = int(identity_number)
        else:
            identity_number = 0
        super().__init__(
            arbitrary_address_capable=int(ecu.attribute(self.ATTR_MAP['arbitrary_address_capable'], default=0)),
            industry_group           =int(ecu.attribute(self.ATTR_MAP['industry_group'], default=0)),
            vehicle_system_instance  =int(ecu.attribute(self.ATTR_MAP['vehicle_system_instance'], default=0)),
            vehicle_system           =int(ecu.attribute(self.ATTR_MAP['vehicle_system'], default=0)),
            function                 =int(ecu.attribute(self.ATTR_MAP['function'], default=0)),
            function_instance        =int(ecu.attribute(self.ATTR_MAP['function_instance'], default=0)),
            ecu_instance             =int(ecu.attribute(self.ATTR_MAP['ecu_instance'], default=0)),
            manufacturer_code        =int(ecu.attribute(self.ATTR_MAP['manufacturer_code'], default=0)),
            identity_number          =identity_number
        )