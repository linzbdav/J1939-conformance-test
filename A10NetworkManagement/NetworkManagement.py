import systest

from utils import ControllerApplication, Name
from . import NetworkManagementTests as NM

def RUN_NM_TESTS(ca:ControllerApplication, dut_name:Name):
    sequencer = systest.setup('A10-NetworkManagement')
    sequencer.run(
        #NM.NM_Test_1(ca, dut_name),
        #NM.NM_Test_2(ca, dut_name),
        NM.NM_Test_3(ca, dut_name),
        #NM.NM_Test_4(ca, dut_name),
        #NM.NM_Test_5(ca, dut_name),
        # Request for Address Claimed / not needed for a sensor
        #NM.NM_Test_7(ca, dut_name),
        #NM.NM_Test_8(ca, dut_name),
        #NM.NM_Test_9(ca, dut_name),
        #NM.NM_Test_10(ca, dut_name),
        #NM.NM_Test_11(ca, dut_name),
        #NM.NM_Test_12(ca, dut_name),
        # Power Interruption
        # Network Disruption
        # Address Continuity
        #NM.NM_Test_16(ca, dut_name),
        # System Notification of continued address violation
        # Name Management
    )
    sequencer.report_and_exit()