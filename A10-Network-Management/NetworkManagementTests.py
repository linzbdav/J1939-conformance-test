import j1939
import time
import systest
from queue import Empty, Queue
import traceback

from ..utils import ControllerApplication, Name

class NM_Base_TestCase(systest.TestCase):
    """ Basic test case for network management tests
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name, name:str) -> None:
        super().__init__(name=name)
        self.dut_name = dut_name
        self.ca = ca
        self.q = Queue()

    def setup(self) -> None:
        super().setup()
        self.ca.callback = self.ca_receive

    def run(self) -> None:
        try:
            self._run()
        except Empty:
            filename, line, _, _ = traceback.extract_stack()[-2]
            raise systest.TestCaseFailedError(f'{filename}:{line}: Timeout on receive queue')

    def _run(self) -> None:
        raise NotImplementedError('Function must be implemented by child class')

    def teardown(self) -> None:
        super().teardown()
        self.ca.callback = None

    def ca_receive(self, priority:int, pgn:int, source:int, timestamp:int, data:bytearray):
        if pgn == 0x00EE00:
            name = j1939.Name(bytes=data[::-1])
            self.q.put({'name': name, 'source': source, 'time': timestamp})


class NM_Test_1(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.2 4.5.8
    Verify the NAME contents for the CA (DUT) align with -81
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='1: CA Name')

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)
        info = self.q.get(timeout=1.25)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)


class NM_Test_2(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5
    Verify each CA transmits an address claim at power-up system initialization
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='2: System Initialization')
    
    def setup(self) -> None:
        super().setup()
        print('Power-Off the DUT')
        input("Press Enter to continue...")
        print('Power-On the DUT')

    def _run(self) -> None:
        info = self.q.get(timeout=10)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.assert_less(info['source'], 0xFE)


class NM_Test_3(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.7.1
    Verify that a non-configurable address CA or service configurable
    address CA stops transmitting and sends a Cannot Claim Address
    message if it fails to claim a valid address.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='3: Non-Configurable Address CA')

    def setup(self) -> None:
        super().setup()
        self.ca.subscribe(self.on_message)

    def _run(self) -> None:
        if self.dut_name.arbitrary_address_capable:
            raise systest.TestCaseSkippedError('Configurable Address CA')
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        src_addr = info['source']
        self.assert_less(src_addr, j1939.ParameterGroupNumber.Address.NULL)
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=src_addr)
        name = info['name']
        name.value = name.value - 1
        self.ca._ecu.send_message(mid.can_id, name.bytes)
        info = self.q.get(timeout=1)
        self.assert_equal(info['source'], j1939.ParameterGroupNumber.Address.NULL)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)

    def teardown(self) -> None:
        self.ca.unsubscribe(self.on_message)
        super().teardown()

    def on_message(self, )


class NM_Test_4(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.6.1
    Verify that a command configurable address CA can receive a Commanded Address message and
    either initiate an address claim procedure with the new address, issue an address claim
    for its current address.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='4: Commanded Addresses')

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)
        
        info = self.q.get(timeout=1)
        self.assert_equal(info['name'].value  & 0xFFFFFFFFFFE00000, self.dut_name.value)

        data = bytearray(info['name'].value.to_bytes(8, byteorder='little'))
        adr = 0x80
        if adr == info['source']:
            adr += 1
        data.append(adr)
        self.ca.send_pgn(0, 0xFE, 0xD8, 7, data)
        info = self.q.get(timeout=1)
        self.assert_equal(info['name'].value  & 0xFFFFFFFFFFE00000, self.dut_name.value)
        self.assert_in(info['source'], [j1939.ParameterGroupNumber.Address.NULL, adr])


class NM_Test_5(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.3.1 4.5.4.3
    Verify that a self-configurable address CA can re-calculate and claim
    another address if it is not successful in claiming the calculated
    address
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='5: Self-Configurable Address CA')

    def _run(self) -> None:
        if self.dut_name.arbitrary_address_capable == 0:
            raise systest.TestCaseSkippedError('Non-Configurable Address CA')
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_not_equal(info['source'], j1939.ParameterGroupNumber.Address.NULL)
        name = info['name']
        src_adr = info['source']
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=src_adr)
        name.value = name.value - 1
        self.ca._ecu.send_message(mid.can_id, name.bytes)

        info = self.q.get(timeout=1)
        self.assert_not_equal(info['source'], j1939.ParameterGroupNumber.Address.NULL)
        self.assert_not_equal(src_adr, info['source'])


class NM_Test_7(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5.3.1
    Verify a CA responds to a request for address claimed sent to the global address
    with an Address Claimed/Cannot Claim message (or nothing if that CA has not yet
    attempted to claim an address).
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='7: Request for Address Claimed (Global)')

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(info['name'].value  & 0xFFFFFFFFFFE00000, self.dut_name.value)
        self.assert_not_equal(info['source'], j1939.ParameterGroupNumber.Address.NULL)


class NM_Test_8(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5.3.2
    Verify a CA responds to a request for address claimed sent to the DUT address 
    with an Address Claimed/Cannot Claim message (or nothing if that CA has not 
    yet attempted to claim an address)
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='8: Request for Address Claimed (Specific)')
        
    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(info['name'].value  & 0xFFFFFFFFFFE00000, self.dut_name.value)
        self.assert_not_equal(info['source'], j1939.ParameterGroupNumber.Address.NULL)
        adr = info['source']
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=adr)
        info = self.q.get(timeout=1)
        self.assert_equal(info['name'].value  & 0xFFFFFFFFFFE00000, self.dut_name.value)
        self.assert_equal(info['source'], adr)


class NM_Test_9(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5
    Verify a CA sends an Address Claimed message upon initialization and waits for the defined
    period before resuming normal network traffic. Single Address CAs with addresses in the 
    0-127 and 248-253 ranges may begin regular network communications immediately after sending
    the address claim message. Other CAs shall not begin or resume origination of normal network
    traffic until 250ms after claiming an address (See J1939-81 Figure A1 of Appendix A) to allow
    contending claims to be made before the address is used.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='9: Address Claimed Cannot Claim')
        self.q2 = Queue()
    
    def setup(self) -> None:
        super().setup()
        print('Power-Off the DUT')
        input("Press Enter to continue...")
        print('Power-On the DUT')
        self.ca.subscribe(self.recv_message)
        
    def _run(self) -> None:
        info1 = self.q.get(timeout=10)
        self.assert_equal(self.dut_name.value, info1['name'].value  & 0xFFFFFFFFFFE00000)
        if info1['source'] <= 127 or (info1['source'] >= 248 and info1['source'] <= 253):
            timeout = 0
        else:
            timeout = 0.250
        info2 = self.q2.get(timeout=1)
        while info2['time'] < info1['time']:
            info2 = self.q2.get(timeout=1)
        self.assert_greater_equal(round(info2['time'] - info1['time'],4), timeout)

        adr = info1['source']
        name = info1['name']
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=adr)
        name.value = name.value - 1
        self.ca._ecu.send_message(mid.can_id, name.bytes)
        info1 = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info1['name'].value  & 0xFFFFFFFFFFE00000)
        info2 = self.q2.get(timeout=1)
        while info2['time'] < info1['time']:
            info2 = self.q2.get(timeout=1)
        self.assert_not_equal(info2['source'], adr)
        self.assert_greater_equal(round(info2['time'] - info1['time'],4), timeout)
    
    def teardown(self) -> None:
        super().teardown()
        self.ca.unsubscribe(self.ca_receive)

    # Callback function for normal messages
    def recv_message(self, priority:int, pgn:int, source:int, timestamp:int, data:int) -> None:
        if pgn == 0xC000 or pgn == 0xC0FF:
            self.q2.put({'time': timestamp, 'source': source, 'data': data})


class NM_Test_10(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5.3.3
    Verify a CA receiving an Address Claimed message with a lower priority claiming
    its own source address responds with an Address Claimed Message
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='10: Address Claimed Cannot Claim')

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)

        adr = info['source']
        name = info['name']
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=adr)
        name.value = name.value + 1
        self.ca._ecu.send_message(mid.can_id, name.bytes)
            
        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.assert_equal(adr, info['source'])


class NM_Test_11(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5.3.3
    Verify a CA receiving an Address Claimed message with a higher priority claiming
    its own source address either attempts to claim a new address or responds with a
    Cannot Claim message after a time delay.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='11: Address Claimed Cannot Claim')
        self.dev_name = None

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.dev_name = info['name'].value

        adr = info['source']
        name = info['name']
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=adr)
        name.value = name.value - 1
        self.ca._ecu.send_message(mid.can_id, name.bytes)
            
        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.assert_not_equal(adr, info['source'])

    def teardown(self) -> None:
        data = bytearray(self.dev_name.to_bytes(8, byteorder='little'))
        data.append(0x80)
        self.ca.send_pgn(0, 0xFE, 0xD8, 7, data)
        time.sleep(0.5)
        super().teardown()


class NM_Test_12(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.5.7
    Verify a CA that cannot claim an address sends the Cannot Claim message
    in response to the Request for Address Claimed. No other messages shall be sent.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> None:
        super().__init__(ca=ca, dut_name=dut_name, name='12: Address Not Claimed')
        self.dev_name = None
        
    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.dev_name = info['name'].value
        adr = info['source']

        while adr < 0xFE:
            name = info['name']
            pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
            mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=adr)
            name.value = name.value - 1
            self.ca._ecu.send_message(mid.can_id, name.bytes)
            
            try:
                info = self.q.get(timeout=1)
                self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
                self.assert_not_equal(adr, info['source'])
                self.assert_not_equal(info['source'], 0xFF)
                adr = info['source']
            except Empty as e:
                if adr == 0xFE:
                    pass
                else:
                    raise e

    def teardown(self) -> None:
        data = bytearray(self.dev_name.to_bytes(8, byteorder='little'))
        data.append(0x80)
        self.ca.send_pgn(0, 0xFE, 0xD8, 7, data)
        time.sleep(0.5)
        super().teardown()


class NM_Test_16(NM_Base_TestCase):
    """ Requiring Document: J1939-81 4.7.2.1
    Verify a CA that receives a messages, other than the address claimed message, which uses
    the CA's own SA, sends the address claim message to the global address but not more often
    than every 5 seconds.
    """
    def __init__(self, ca:ControllerApplication, dut_name:Name) -> Name:
        super().__init__(ca=ca, dut_name=dut_name, name='16: Address Violation response')

    def _run(self) -> None:
        self.ca.send_request(data_page=0, pgn=0x00EE00, destination=0xFF)

        info = self.q.get(timeout=1)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        adr = info['source']
        time.sleep(1.25)
        pgn = j1939.ParameterGroupNumber(0, 0xC0, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=adr)
        self.ca._ecu.send_message(mid.can_id, [0,0,0,0,0,0,0,0])
            
        info = self.q.get(timeout=0.25)
        self.assert_equal(self.dut_name.value, info['name'].value & 0xFFFFFFFFFFE00000)
        self.assert_not_equal(adr, info['source'])