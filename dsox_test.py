import remotevisa
import time
import numpy as np
import matplotlib.pyplot as plt

remotevisa.commsMan = remotevisa.CommsManager()
remotevisa.commsMan.StartCommunications("143.106.153.67", 8080)
# remotevisa.commsMan.ResetVisa()

rm = remotevisa.ResourceManager()
res_list = rm.list_resources()
print(res_list)

dev_id = ""
dev = remotevisa.Resource()
for i in range(len(res_list)):
    if ("0x2A8D" in res_list[i]) and ("0x0396" in res_list[i]):
        dev_id = res_list[i]
        break

if dev_id != "":
    del dev
    dev = rm.open_resource(dev_id)


print(dev.query("*IDN?"))

print(dev.query("CHAN2:PROB?"))
print(dev.query("CHAN2:RANG?"))
print(dev.query("CHAN2:OFFS?"))
print(dev.query("TIM:MODE?"))
print(dev.query("TIM:RANG?"))
print(dev.query("TIM:DEL?"))
print(dev.query("TIM:REF?"))
print(dev.query("ACQ:MODE?"))
print(dev.query("TRIG:SOUR?"))

print()
dev.write("WAV:SOUR CHAN2")
dev.write("WAV:FORM WORD")
dev.write("WAV:UNS 1")

print(dev.query("WAV:SOUR?"))
print(dev.query("WAV:FORM?"))

endianess = dev.query("WAV:BYT?")
points = int(dev.query("WAV:POIN?"))
xinc = float(dev.query("WAV:XINC?"))
x0 = float(dev.query("WAV:XOR?"))
xref = int(dev.query("WAV:XREF?"))
yinc = float(dev.query("WAV:YINC?"))
y0 = float(dev.query("WAV:YOR?"))
yref = float(dev.query("WAV:YREF?"))

print(endianess)
print(points)
print(xinc, x0, xref)
print(yinc, y0, yref)

if endianess == "MSBF":
    big_endian = True
else:
    big_endian = False

t0 = time.time()
bytes_array = np.array(dev.query_binary_values("WAV:DATA?", datatype='H', is_big_endian=big_endian))
y_data = (bytes_array - yref)*yinc + y0
print(time.time() - t0)

dev.write("WAV:FORM ASC")
asc_data = dev.query("WAV:DATA?")
double_spaces = True
while double_spaces:
    asc_data = asc_data.replace("  ", " ")
    double_spaces = ("  " in asc_data)
asc_array = asc_data.replace(",", "").split(" ")
data2_array = np.asarray(asc_array[1:], dtype=float)

x_data = (np.linspace(0, points - 1, points) - xref)*xinc + x0

plt.plot(x_data, y_data)
plt.plot(x_data, data2_array)
plt.show()





dev.close()
remotevisa.commsMan.CloseCommunications()