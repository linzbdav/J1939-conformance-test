import j1939
import time
import canmatrix
import tkinter as tk
from tkinter import filedialog

from utils.ControllerApplication import ControllerApplication
from utils.Name import Name
from A10NetworkManagement.NetworkManagement import RUN_NM_TESTS

root = tk.Tk()
root.withdraw()

file_path = filedialog.askopenfilename(title = "Select file", initialdir='support_files', filetypes=(("DBC Files","*.dbc"),))
if file_path:

    db = canmatrix.formats.loadp_flat(file_path)
    cas = []
    for ecu in db.ecus:
        if ecu.name != 'DUT':
            dbs = canmatrix.CanMatrix()
            canmatrix.copy.copy_ecu_with_frames(ecu, db, dbs)
            cas.append(ControllerApplication(dbs, Name(ecu), int(ecu.attribute('NmStationAddress'))))

    ecu = j1939.ElectronicControlUnit(max_cmdt_packets=0xFF)
    ecu.connect(bustype='ixxat', channel=0, bitrate=250000)

    # Start all cas
    for ca in cas:
        ecu.add_ca(controller_application=ca)
        ca.start()

    db_ecu = db.ecu_by_name('DUT')
    dut_name = Name(db_ecu)

    # Wait until cas are ready
    for ca in cas:
        while ca.state != j1939.ControllerApplication.State.NORMAL:
            time.sleep(0.1)
    
    ca = cas[0] # Consider only first controller application

    try:
        RUN_NM_TESTS(ca, dut_name)
    except Exception as e:
        print(e)
    finally:
        ca.stop()
        ecu.disconnect()
else:
    print('No file selected.')