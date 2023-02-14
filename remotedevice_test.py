import agilent816xb
import keysightDSOX1200
import time
import numpy as np
import matplotlib.pyplot as plt

# Import this for remote support
from remotevisa import CommsManager

# And start communications
commsMan = CommsManager()
commsMan.StartCommunications("143.106.153.67", 8080)
commsMan.ResetVisa()

# These arguments enable remote communications. That's it!
dev1 = agilent816xb.Agilent816xb(True, commsMan) 
dev1.connect(True, 20, False)

dev2 = keysightDSOX1200.KeysightDSOX1200(True, commsMan)
dev2.connect()

print(dev1.devID)
print(f"On: {dev1.getState(0)}")
print(f"Wavelength: {dev1.getWL(0)} nm")
print(f"Power: {dev1.getPwr(0)} dBm")
print()

sw_start = 1558.5
sw_stop = 1558.7
sw_speed = 0.5

dev1.setState(0, True)
dev1.setPwr(0, 1)
dev1.setSweep(0, 'CONT', sw_start, sw_stop, 1, 0, 0, sw_speed)
dev1.setSweepState(0, "Start")

print()
print(dev2.devID)
dev2.dev.timeout = 500

sw_time = (sw_stop - sw_start)/sw_speed
time_range = 1.1*sw_time
time_delay = sw_time/10.0

dev2.dev.clear()
dev2.SetTimeMode("MAIN")
dev2.SetAcqMode("RTIM")
dev2.SetAcqType("NORM")
dev2.SetTimeRef("LEFT")

dev2.SetProbe(1, 2)
dev2.SetCoupling(2, "AC")
dev2.SetRange(3, 2)
dev2.SetOffset(0.15, 2)

dev2.SetTriggerSource("EXT")
dev2.SetTriggerMode("EDGE")
dev2.SetTriggerSlope("POS")
dev2.SetTriggerSweep("NORM")
dev2.SetTriggerLevel(1.0)

dev2.SetTimeRange(time_range)
dev2.SetTimeDelay(time_delay)
t0 = time.time()
dev2.PrepareWait()
dev2.Digitize()
dev2.WaitOperation(0.2, 50)
print(f"Osc time: {time.time() - t0:.3f} s")

data_t = dev2.GetDataX(1)
data_wl = sw_start + data_t*sw_speed
start_index = np.abs(data_wl - sw_start).argmin()
stop_index = np.abs(data_wl - sw_stop).argmin() + 1

t0 = time.time()
data_y2 = dev2.GetDataY_BIN(2)
print(f"BIN time: {time.time() - t0:.3f} s")

# data_y1 = dev2.GetDataY_BIN(1)

fig, ax = plt.subplots(1, 1)
# ax.plot(data_wl[start_index:stop_index], data_y1[start_index:stop_index])
ax.plot(data_wl[start_index:stop_index], data_y2[start_index:stop_index])
ax.set_xlabel("Wavelength (nm)")
ax.set_ylabel("Voltage (V)")
ax.get_xaxis().get_major_formatter().set_useOffset(False)

# t0 = time.time()
# data_y2a = dev2.GetDataY_ASC(2)
# print(f"ASC time: {time.time() - t0:.3f} s")
# ax.plot(data_wl[start_index:stop_index], data_y2a[start_index:stop_index])

plt.show()

dev1.setSweepState(0, "Stop")
dev1.setState(0, False)
dev1.close()
dev2.close()
commsMan.CloseCommunications()