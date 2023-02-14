# -*- coding: utf-8 -*-
import numpy as np
import time

visa = None

class KeysightDSOX1200:
    # definitions
    remote = False
    gpib = False
    eth = False
    usb = True
    gpibAddr = 17
    ip = "192.168.1.2"
    port = 10001
    visarm = None
    visaOK = False
    dev = None
    devOK = False
    devID = ""
    usbid_hex = "0x2A8D::0x0396"
    usbid_dec = "10893::918"
    
    init_ESE = 255

    # main functions
    def __init__(self, remote=False, rem_comm_man=None):
        # This block is the only change needed to implement remote VISA support!
        self.remote = remote
        if self.remote:
            import remotevisa as visa
            visa.commsMan = rem_comm_man
            if rem_comm_man == None:
                print("Error: Remote is set to True, but no communication manager given! Create and start communications" + 
                      "with commsMan = remotevisa.CommsManager() and initialize communications." + 
                      "Then, create this object with it as argument.")
        else:
            import pyvisa as visa

        try:
            self.visarm = visa.ResourceManager()
            self.visaOK = True
        except:
            print("Error creating VISA Resource Manager! Are the VISA libraries installed?")

        if not self.visaOK:
            try:
                self.visarm = visa.ResourceManager('@py')
                self.visaOK = True
            except:
                print("Error creating VISA Resource Manager! Are the VISA libraries installed?")

    def __del__(self):
        self.close()
        return 0

    def connect(self, isgpib=False, address=17, iseth=False, ethip="192.168.1.1", ethport=10001, isusb=True):
        if self.visaOK:
            self.gpib = isgpib
            self.gpibAddr = address
            self.eth = iseth
            self.ip = ethip
            self.port = ethport
            self.usb = isusb
            try:
                if self.gpib:
                    name = "GPIB0::" + str(self.gpibAddr) + "::INSTR"
                    self.dev = self.visarm.open_resource(name)
                elif self.eth:
                    name = "TCPIP0::" + self.ip + "::INSTR"
                    self.dev = self.visarm.open_resource(name, read_termination="\r\n", timeout=5000)
                elif self.usb:
                    devs_list = self.visarm.list_resources()
                    for dev_name in devs_list:
                        if (self.usbid_hex in dev_name) or (self.usbid_dec in dev_name):
                            self.dev = self.visarm.open_resource(dev_name)
                            break
                
                self.devID = self.dev.query("*IDN?")
                if "DSOX" in self.devID:
                    self.devOK = True
                else:
                    print("Error opening device! Is it connected?")
            except:
                print("Error opening device! Is it connected?")
                pass

    def init(self):
        pass

    def close(self):
        if self.devOK:
            self.devOK = False
            if not self.remote:
                self.dev.close()

    def GetPoints(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            curr_chan = self.dev.query("WAV:SOUR?")
            self.dev.write(f"WAV:SOUR CHAN{chan}")
            resp = self.dev.query(f"WAV:POIN?")
            self.dev.write(f"WAV:SOUR {curr_chan}")
            points = int(resp)
            return points
        else:
            return 0

    def SetCoupling(self, chan=1, coupl="DC"):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            if coupl == "DC" or coupl=="AC":
                self.dev.write(f"CHAN{chan}:COUP {coupl}")

    def GetCoupling(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            resp = self.dev.query(f"CHAN{chan}:COUP?")
            return resp
        else:
            return ""

    def SetProbe(self, val, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            if val < 0.1: val = 0.1
            if val > 10000: val - 10000

            self.dev.write(f"CHAN{chan}:PROB {val}")

    def GetProbe(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            resp = self.dev.query(f"CHAN{chan}:PROB?")
            return float(resp)
        else:
            return 0

    def SetRange(self, val, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            self.dev.write(f"CHAN{chan}:RANG {np.abs(val)}")

    def GetRange(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            resp = self.dev.query(f"CHAN{chan}:RANG?")
            return float(resp)
        else:
            return ""

    def SetOffset(self, val, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            self.dev.write(f"CHAN{chan}:OFFS {np.abs(val)}")

    def GetOffset(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            resp = self.dev.query(f"CHAN{chan}:OFFS?")
            return float(resp)
        else:
            return 0

    def SetTimeMode(self, mode="MAIN"):
        if self.devOK:
            if mode=="MAIN" or mode=="WIND" or mode=="XY" or mode=="ROLL":
                self.dev.write(f"TIM:MODE {mode}")

    def GetTimeMode(self):
        if self.devOK:
            resp = self.dev.query(f"TIM:MODE?")
            return resp
        else:
            return ""

    def SetTimeRange(self, val):
        if self.devOK:
            self.dev.write(f"TIM:RANG {np.abs(val)}")

    def GetTimeRange(self):
        if self.devOK:
            resp = self.dev.query(f"TIM:RANG?")
            return float(resp)
        else:
            return 0

    def SetTimeDelay(self, val):
        if self.devOK:
            self.dev.write(f"TIM:DEL {val}")

    def GetTimeDelay(self):
        if self.devOK:
            resp = self.dev.query(f"TIM:DEL?")
            return float(resp)
        else:
            return 0

    def SetTimeRef(self, mode="LEFT"):
        if self.devOK:
            if mode=="LEFT" or mode=="CENTER" or mode=="RIGHT":
                self.dev.write(f"TIM:REF {mode}")

    def GetTimeRef(self):
        if self.devOK:
            resp = self.dev.query(f"TIM:REF?")
            return resp
        else:
            return ""

    def SetAcqMode(self, mode="RTIM"):
        if self.devOK:
            if mode=="RTIM" or mode=="SEGM":
                self.dev.write(f"ACQ:MODE {mode}")

    def GetAcqMode(self):
        if self.devOK:
            resp = self.dev.query(f"ACQ:MODE?")
            return resp
        else:
            return ""

    def SetAcqType(self, mode="NORM"):
        if self.devOK:
            if mode=="NORM" or mode=="AVER" or mode=="HRES" or mode=="PEAK":
                self.dev.write(f"ACQ:TYPE {mode}")

    def GetAcqType(self):
        if self.devOK:
            resp = self.dev.query(f"ACQ:TYPE?")
            return resp
        else:
            return ""

    def SetAvgs(self, val):
        if self.devOK:
            if val < 1: val = 1
            if val > 65536: val = 65536
            self.dev.write(f"ACQ:COUN {int(val)}")

    def GetAvgs(self):
        if self.devOK:
            resp = self.dev.query(f"ACQ:COUN?")
            return int(resp)
        else:
            return 0

    def SetTriggerSource(self, src="EXT"):
        if self.devOK:
            if "CHAN" in src or src=="EXT" or src=="LINE" or src=="WGEN":
                self.dev.write(f"TRIG:SOUR {src}")

    def GetTriggerSource(self):
        if self.devOK:
            resp = self.dev.query(f"TRIG:SOUR?")
            return resp
        else:
            return ""

    def SetTriggerMode(self, mode="EDGE"):
        if self.devOK:
            if mode=="EDGE" or mode=="GLITCH" or mode=="PATT" or mode=="SHOL" or mode=="TRAN" or mode=="TV" or mode=="SBUS1":
                self.dev.write(f"TRIG:MODE {mode}")

    def GetTriggerMode(self):
        if self.devOK:
            resp = self.dev.query(f"TRIG:MODE?")
            return resp
        else:
            return ""

    def SetTriggerSweep(self, mode="NORM"):
        if self.devOK:
            if mode=="NORM" or mode=="AUTO":
                self.dev.write(f"TRIG:SWE {mode}")

    def GetTriggerSweep(self):
        if self.devOK:
            resp = self.dev.query(f"TRIG:SWE?")
            return resp
        else:
            return ""

    def SetTriggerLevel(self, val):
        if self.devOK:
            self.dev.write(f"TRIG:LEV {val}")

    def GetTriggerLevel(self):
        if self.devOK:
            resp = self.dev.query(f"TRIG:LEV?")
            return float(resp)
        else:
            return 0

    def SetTriggerSlope(self, mode="POS"):
        if self.devOK:
            if mode=="POS" or mode=="NEG" or mode=="EITH" or mode=="ALT":
                self.dev.write(f"TRIG:SLOP {mode}")

    def GetTriggerSlope(self):
        if self.devOK:
            resp = self.dev.query(f"TRIG:SLOP?")
            return resp
        else:
            return ""

    def Digitize(self, chan=0):
        if self.devOK:
            if chan == 0:
                self.dev.write(f"DIG")
            else:
                chan = (int(np.abs(chan)) % 5)
                self.dev.write(f"DIG CHAN{chan}")

    def Single(self):
        if self.devOK:
            self.dev.write(f"SING")

    def Stop(self):
        if self.devOK:
            self.dev.write(f"STOP")

    def Run(self):
        if self.devOK:
            self.dev.write(f"RUN")

    def GetDataX(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            self.dev.write(f"WAV:SOUR CHAN{chan}")
            points = self.GetPoints(chan)
            xinc = float(self.dev.query("WAV:XINC?"))
            x0 = float(self.dev.query("WAV:XOR?"))
            xref = int(self.dev.query("WAV:XREF?"))
            x_data = (np.linspace(0, points - 1, points) - xref)*xinc + x0

            return x_data
        else:
            return np.zeros(101)

    def GetDataY_BIN(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            self.dev.write(f"WAV:SOUR CHAN{chan}")
            self.dev.write("WAV:FORM WORD")
            self.dev.write("WAV:UNS 1")
            endianess = self.dev.query("WAV:BYT?")
            yinc = float(self.dev.query("WAV:YINC?"))
            y0 = float(self.dev.query("WAV:YOR?"))
            yref = float(self.dev.query("WAV:YREF?"))
            if endianess == "MSBF":
                big_endian = True
            else:
                big_endian = False
            
            bytes_array = np.array(self.dev.query_binary_values("WAV:DATA?", datatype='H', is_big_endian=big_endian))
            y_data = (bytes_array - yref)*yinc + y0

            return y_data
        else:
            return np.zeros(101)

    def GetDataY_ASC(self, chan=1):
        if self.devOK:
            chan = (int(np.abs(chan)) % 5)
            self.dev.write(f"WAV:SOUR CHAN{chan}")
            self.dev.write("WAV:FORM ASC")
            asc_data = self.dev.query("WAV:DATA?")
            double_spaces = True
            while double_spaces:
                asc_data = asc_data.replace("  ", " ")
                double_spaces = ("  " in asc_data)
            asc_array = asc_data.replace(",", "").split(" ")
            y_data = np.asarray(asc_array[1:], dtype=float)

            return y_data
        else:
            return np.zeros(101)

    def PrepareWait(self):
        self.dev.write("STOP")
        self.dev.query("*ESR?")
        self.dev.query("*OPC?")
        # self.init_ESE = int(self.dev.query("*ESE?"))
        # self.dev.write("*ESE 1")
    
    def WaitOperation(self, interval=1.0, max_n=20):
        self.dev.write("*OPC")
        
        complete = False
        n = 0
        stb0 = 0
        changes = 0
        while (not complete) and n < max_n:
            stb = int(self.dev.read_stb())
            print(stb, changes)
            if n == 0:
                stb0 = stb
            else:
                if stb != stb0:
                    stb0 = stb
                    changes += 1
            complete = changes > 0
            n += 1
            time.sleep(interval)

        self.dev.query("*ESR?")
        # self.dev.write(f"*ESE {self.init_ESE}")

    def ReadSystError(self):
        return self.dev.query("SYST:ERR?")