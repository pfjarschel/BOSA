# -*- coding: utf-8 -*-

"""
Created on Tue Dec 13 14:19 2022

@author: pfjarschel
"""

import sys, time, ctypes, os.path
import threading
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5 import uic
from PyQt5.QtCore import Qt, QObject, QTimer, QDir
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QRadioButton, QMessageBox
from PyQt5.QtGui import QIcon

from remotevisa import CommsManager
from agilent816xb import Agilent816xb
from keysightDSOX1200 import KeysightDSOX1200

FormUI, WindowUI = uic.loadUiType("MainWindow.ui")


class MainWindow(FormUI, WindowUI):

    def __init__(self):
        super(MainWindow, self).__init__()
        
        # Variables
        self.settingsfile = "last_settings.json"
        self.fullpath = str(__file__)
        self.lastdir = QDir.homePath()
        self.inited = False
        self.recalc = False
        self.frecalc = False
        self.osc_started = False
        self.osc_stb0 = -1
        self.osc_stb_changes = 0
        self.sweeping = False
        self.has_data = False
        self.busy = False
        self.willstop = False
        self.autorange_started = False
        self.autorange_approach = False

        self.c = 2.99792458e5
        self.minWl = 1494.0
        self.maxWl = 1641.0
        self.minSpan = 0.001
        self.maxSpan = self.maxWl - self.minWl
        self.maxStart = self.maxWl - self.minSpan
        self.minStop = self.minWl + self.minSpan
        self.minCenter = self.minWl + self.minSpan/2.0
        self.maxCenter = self.maxWl - self.minSpan/2.0
        
        # Measurement vars
        self.x_results = np.zeros(101)
        self.wls = np.zeros(101)
        self.freqs = np.zeros(101)
        self.y_results = np.zeros(101)
        self.volts = np.zeros(101)
        self.mW = np.zeros(101)
        self.dbm = np.zeros(101)
        self.avgs = []
        
      
        # Set up
        self.setupUi(self)
        self.SetupActions()
        self.loadSettings()
        self.setupOtherUi()
        
        self.show()
        resizeEvent = self.OnWindowResize
        self.setWindowIcon(QIcon("spectrum.ico"))

        # Devices
        self.commsMan = CommsManager()
        self.osc = None
        self.laser = None
        self.InitializeDevices()
        self.UpdateGraph()

    def OnWindowResize(self, event):
        pass

    def setupOtherUi(self):
        self.statusbar.showMessage(f"Initializing...")

        self.figure = plt.figure()
        self.graph = FigureCanvas(self.figure)
        self.graphToolbar = NavigationToolbar(self.graph, self)
        self.graphHolder.addWidget(self.graphToolbar)
        self.graphHolder.addWidget(self.graph)
        self.graph_ax = self.figure.add_subplot()
        self.graph_line, = self.graph_ax.plot(self.x_results, self.y_results)
        self.graph_ax.set_xlabel("Wavelength (nm)")
        self.graph_ax.set_ylabel("Volts (V)")
        self.graph_ax.set_title("Brillouin Spectrum")
        self.graph_ax.grid(True)
        self.graph_ax.get_xaxis().get_major_formatter().set_useOffset(False)
        self.graph.draw()

        if self.nmRadio.isChecked():
            self.xscaleStack.setCurrentIndex(0)
        elif self.thzRadio.isChecked():
            self.xscaleStack.setCurrentIndex(1)

        self.autorangeCheck.setChecked(False)

    def SetupActions(self):
        # Buttons and etc
        self.runBut.clicked.connect(self.Run)
        self.stopBut.clicked.connect(self.StopButton)
        self.saveBut.clicked.connect(self.OnSaveResults)
        self.startSpin.valueChanged.connect(self.OnStartStopChanged)
        self.stopSpin.valueChanged.connect(self.OnStartStopChanged)
        self.centerSpin.valueChanged.connect(self.OnCenterSpanChanged)
        self.spanSpin.valueChanged.connect(self.OnCenterSpanChanged)
        self.startfSpin.valueChanged.connect(self.OnFreqChanged)
        self.stopfSpin.valueChanged.connect(self.OnFreqChanged)
        self.centerfSpin.valueChanged.connect(self.OnFreqChanged)
        self.spanfSpin.valueChanged.connect(self.OnFreqChanged)
        self.speedSpin.valueChanged.connect(self.OnSpeedChanged)
        self.powerSpin.valueChanged.connect(self.OnPowerChanged)
        self.oscchanSpin.valueChanged.connect(self.OnOscYChanged)
        self.couplingCombo.currentIndexChanged.connect(self.OnOscYChanged)
        self.rangeSpin.valueChanged.connect(self.OnOscYChanged)
        self.offsetSpin.valueChanged.connect(self.OnOscYChanged)
        self.autorangeCheck.toggled.connect(self.OnAutoRangeToggled)
        self.triggerCombo.currentIndexChanged.connect(self.OnTriggerChanged)
        self.triglvSpin.valueChanged.connect(self.OnTriggerChanged)
        self.acqCombo.currentIndexChanged.connect(self.OnAcquisitionChanged)
        self.voltRadio.clicked.connect(self.OnChangeYScale)
        self.linRadio.clicked.connect(self.OnChangeYScale)
        self.dbRadio.clicked.connect(self.OnChangeYScale)
        self.nmRadio.clicked.connect(self.OnChangeXScale)
        self.thzRadio.clicked.connect(self.OnChangeXScale)
        
        self.actionSave_config.triggered.connect(self.OnSaveSettings)
        self.actionLoad_config.triggered.connect(self.OnLoadSettings)
        self.actionSave_final_results.triggered.connect(self.OnSaveResults)
        self.actionExit.triggered.connect(self.Exit)
        self.actionAbout.triggered.connect(self.About)

        # Timers
        self.measTimer = QTimer()
        self.measTimer.timeout.connect(self.measLoop)
        self.measTimer.setInterval(1000)

    def InitializeDevices(self):
        self.statusbar.showMessage(f"Initializing...")
        error_text = ""
        statusmsg = ""

        # Start communications
        self.commsMan.StartCommunications("143.106.153.67", 8080)
        self.commsMan.ResetVisa()

        self.osc = KeysightDSOX1200(True, self.commsMan)
        self.osc.connect()
        osc_ok = self.osc.devOK
        self.osc.dev.timeout = 10000
        if osc_ok:
            statusmsg += "Oscilloscope OK! "
        else:
            error_text += ("Error communicating with the oscilloscope! " + 
                           "Check if it is connected and succesfully detected by the computer!\n\n")
            statusmsg += "Oscilloscope ERROR! "
        
        self.laser = Agilent816xb(True, self.commsMan)
        self.laser.connect(True, 20, False)
        laser_ok = self.laser.devOK
        if laser_ok:
            statusmsg += "Laser OK! "
        else:
            error_text += ("Error communicating with the laser! " +
                           "Check if it is connected and succesfully detected by the computer!\n\n")
            statusmsg += "Laser ERROR! "
        
        if self.osc.devOK and self.laser.devOK:
            statusmsg = "Devices OK!"

        # Devices status
        if error_text != "":
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Errors found while initializing devices:")
            msg.setInformativeText(error_text)
            msg.setWindowTitle("Error")
            msg.exec_()              

        self.statusbar.showMessage(statusmsg)
        self.inited = True
        
    def Run(self):
        if not self.sweeping and self.inited:
            self.statusbar.showMessage(f"Preparing...")

            self.willstop = False
            
            sw_start = self.startSpin.value()
            sw_stop = self.stopSpin.value()
            sw_speed = self.speedSpin.value()

            self.laser.setState(0, True)
            self.laser.setPwr(0, self.powerSpin.value())
            self.laser.setSweep(0, 'CONT', sw_start, sw_stop, 1, 0, 0, sw_speed)
            self.laser.setSweepState(0, "Start")

            sw_time = (sw_stop - sw_start)/sw_speed
            time_range = 1.1*sw_time
            time_delay = sw_time/10.0

            chan = self.oscchanSpin.value()
            self.osc.dev.clear()
            self.osc.SetTimeMode("MAIN")
            self.osc.SetAcqMode("RTIM")
            self.osc.SetTimeRef("LEFT")
            self.osc.SetProbe(1, chan)
            self.osc.SetTriggerMode("EDGE")
            self.osc.SetTriggerSlope("POS")
            self.osc.SetTriggerSweep("NORM")
            self.osc.SetTimeRange(time_range)
            self.osc.SetTimeDelay(time_delay)

            self.osc.SetAcqType(self.acqCombo.currentText())
            self.osc.SetCoupling(chan, self.couplingCombo.currentText())
            self.osc.SetRange(self.rangeSpin.value(), chan)
            self.osc.SetOffset(self.offsetSpin.value(), chan)
            self.osc.SetTriggerSource(self.triggerCombo.currentText())
            self.osc.SetTriggerLevel(self.triglvSpin.value())
            self.osc_started = False
            self.osc_stb0 = -1
            self.osc_stb_changes = 0

            self.sweeping = True
            self.UpdateGraph()
            self.measTimer.setInterval(200)
            self.measTimer.start()

            self.statusbar.showMessage(f"Running...")

    def threadLoop(self):
        self.busy = True

        if not self.osc_started:
            self.osc.PrepareWait()
            self.osc.Digitize()
            self.osc.dev.write("*OPC")
            self.osc_stb0 = -1
            self.osc_stb_changes = 0
            self.osc_started = True

            self.statusbar.showMessage(f"Starting acquisition...")
        else:
            stb = int(self.osc.dev.read_stb())
            if self.osc_stb0 < 0:
                self.osc_stb0 = stb
            else:
                if stb != self.osc_stb0:
                    self.osc_stb0 = stb
                    self.osc_stb_changes += 1
                else:
                    if stb == 165:
                        self.osc.dev.clear()
                        self.osc_started = False
                        self.busy = False
                        return              

                if self.osc_stb_changes > 0:
                    self.statusbar.showMessage(f"Acquisition complete!")

                    self.osc.dev.query("*ESR?")

                    data_t = self.osc.GetDataX(self.oscchanSpin.value())
                    data_wl = self.startSpin.value() + data_t*self.speedSpin.value()
                    start_index = np.abs(data_wl - self.startSpin.value()).argmin()
                    stop_index = np.abs(data_wl - self.stopSpin.value()).argmin() + 1
                    data_y = self.osc.GetDataY_BIN(self.oscchanSpin.value())

                    if data_t.min() != data_t.max:
                        self.has_data = True
                    else:
                        self.has_data = False
                    
                    avgn = self.avgSpin.value()
                    
                    if avgn > 1:
                        if len(self.avgs) < avgn:
                            self.avgs.append(data_y)
                        elif len(self.avgs) > avgn:
                            self.avgs = self.avgs[:avgn]
                        else:
                            self.avgs.append(self.avgs.pop(0))
                            self.avgs[-1] = data_y

                        data_y = np.average(self.avgs, 0)
                    
                    self.volts = data_y[start_index:stop_index]
                    self.mW = self.volts/self.calSpin.value()
                    self.dbm = 10*np.log10(np.clip(self.mW, a_min=10**(self.dbclipSpin.value()/10.0), a_max=None))
                    
                    self.wls = data_wl[start_index:stop_index]
                    self.freqs = self.c/self.wls

                    self.UpdateGraph()

                    self.AutoRangeOffs()

                    self.osc_started = False
                else:
                    self.statusbar.showMessage(f"Acquisition in progress...")
        self.busy = False   
    
    def measLoop(self):
        if self.sweeping and self.inited and not self.busy:
            if self.willstop:
                self.Stop()
            else:
                t1 = threading.Thread(target=self.threadLoop)
                t1.start()
            
    def StopButton(self):
        if self.sweeping and self.inited:
            self.willstop = True
    
    def Stop(self):
        if self.sweeping and self.inited:
            self.sweeping = False
            self.measTimer.stop()
            self.laser.setSweepState(0, "Stop")
            self.laser.setState(0, False)
            self.statusbar.showMessage(f"Sweep stopped")
            
    def UpdateGraph(self):
        if self.voltRadio.isChecked():
            self.y_results = self.volts
            self.graph_ax.set_ylabel("Voltage (V)")
        elif self.linRadio.isChecked():
            self.y_results = self.mW
            self.graph_ax.set_ylabel("Power (mW)")
        elif self.dbRadio.isChecked():
            self.y_results = self.dbm
            self.graph_ax.set_ylabel("Power (dBm)")

        if self.nmRadio.isChecked():
            self.x_results = self.wls
            self.graph_ax.set_xlabel("Wavelength (nm)")
        elif self.thzRadio.isChecked():
            self.x_results = self.freqs
            self.graph_ax.set_xlabel("Frequency (THz)")

        self.graph_line.set_xdata(self.x_results)
        self.graph_line.set_ydata(self.y_results)
        self.graph_ax.autoscale_view(True,True,True)
        self.graph_ax.relim()
        self.figure.canvas.draw()
        self.figure.canvas.flush_events()
    
    def RescaleX(self, margin=0.0):
        if self.has_data:
            lo, hi = self.graph_ax.get_xlim()
            new_lo = lo
            new_hi = hi
            if self.nmRadio.isChecked() and lo < 1000:
                new_lo = self.c/hi
                new_hi = self.c/lo
            elif self.thzRadio.isChecked() and lo > 1000:
                new_lo = self.c/hi
                new_hi = self.c/lo
            self.graph_ax.set_xlim(new_lo, new_hi)

    def RescaleY(self, margin=0.1):
        if self.has_data:
            h = np.max(self.y_results) - np.min(self.y_results)
            bot = np.min(self.y_results) - margin*h
            top = np.max(self.y_results) + margin*h
            self.graph_ax.set_ylim(bot, top)

    def OnAutoRangeToggled(self):
        self.autorange_started = False
        self.autorange_approach = False
        if self.autorangeCheck.isChecked():
            self.rangeSpin.setEnabled(False)
            self.offsetSpin.setEnabled(False)
        else:
            self.rangeSpin.setEnabled(True)
            self.offsetSpin.setEnabled(True)
    
    def AutoRangeOffs(self):
        if self.autorangeCheck.isChecked():
            max_range = 20
            margin = 0.2
            vrange = self.rangeSpin.value()
            voffs = self.offsetSpin.value()
            vtop = vrange/2.0 + voffs
            vbot = -vrange/2.0 + voffs
            vmax = self.volts.max()
            vmin = self.volts.min()

            if not self.autorange_started:
                self.rangeSpin.setValue(max_range)
                self.offsetSpin.setValue(0.0)
                self.autorange_started = True
                self.autorange_approach = True
            elif self.autorange_approach:
                if (vmax - vmin) < vrange/4.0:
                    new_range = (4 - margin)*(vmax - vmin)
                    new_offs = vmax - (vmax - vmin)/2.0
                    self.rangeSpin.setValue(new_range)
                    self.offsetSpin.setValue(new_offs)
                elif (vmax - vmin) > vrange/4.0 and (vmax - vmin) < vrange/2.0:
                    new_range = (2 - margin)*(vmax - vmin)
                    new_offs = vmax - (vmax - vmin)/2.0
                    self.rangeSpin.setValue(new_range)
                    self.offsetSpin.setValue(new_offs)
                else:
                    new_range = (1 + margin)*(vmax - vmin)
                    new_offs = vmax - (vmax - vmin)/2.0
                    self.rangeSpin.setValue(new_range)
                    self.offsetSpin.setValue(new_offs)
                    self.autorange_approach = False               
            else:
                if vmax - vmin > (1 - margin)*vrange:
                    new_range = (vmax - vmin)*(1 + margin)
                    self.rangeSpin.setValue(new_range)
                elif vmax - vmin < (1 - 2*margin)*vrange:
                    new_range = (vmax - vmin)*(1 + margin)
                    self.rangeSpin.setValue(new_range)
                else:
                    #if vmax > (1 - margin/2.0)*vtop or vmin < (1 - margin/2.0)*vbot:
                    if np.abs(vtop - vmax)/np.abs(vmin - vbot) > (1 + margin/2.0) or \
                       np.abs(vtop - vmax)/np.abs(vmin - vbot) < (1 - margin/2.0):
                        new_offs = vmax - (vmax - vmin)/2.0
                        self.offsetSpin.setValue(new_offs)
    
    def OnStartStopChanged(self):
        if not self.recalc:
            self.recalc = True
            
            was_sweeping = self.sweeping
            if was_sweeping:
                self.measTimer.stop()
                self.laser.setSweepState(0, "Stop")

            sender = self.sender()
            if (sender == self.startSpin):
                if self.startSpin.value() > self.maxStart: self.startSpin.setValue(self.maxStart)
                if self.startSpin.value() < self.minWl: self.startSpin.setValue(self.minWl)
                if self.stopSpin.value() <= self.startSpin.value():
                    self.stopSpin.setValue(self.startSpin.value() + self.minSpan)
            
            elif (sender == self.stopSpin):
                if self.stopSpin.value() > self.maxWl: self.stopSpin.setValue(self.maxWl)
                if self.stopSpin.value() < self.minStop: self.stopSpin.setValue(self.minStop)
                if self.startSpin.value() >= self.stopSpin.value():
                    self.startSpin.setValue(self.stopSpin.value() - self.minSpan)
                        
            self.centerSpin.setValue((self.stopSpin.value() + self.startSpin.value())/2.0)
            self.spanSpin.setValue(self.stopSpin.value() - self.startSpin.value())

            self.startfSpin.setValue(self.c/self.stopSpin.value())
            self.stopfSpin.setValue(self.c/self.startSpin.value())
            self.centerfSpin.setValue(self.c/self.centerSpin.value())
            self.spanfSpin.setValue(self.stopfSpin.value() - self.startfSpin.value())

            self.recalc = False
            if was_sweeping:
                sw_start = self.startSpin.value()
                sw_stop = self.stopSpin.value()
                sw_speed = self.speedSpin.value()
                sw_time = (sw_stop - sw_start)/sw_speed
                time_range = 1.1*sw_time
                time_delay = sw_time/10.0
                self.laser.setSweep(0, 'CONT', sw_start, sw_stop, 1, 0, 0, sw_speed)
                self.osc.SetTimeRange(time_range)
                self.osc.SetTimeDelay(time_delay)
                self.laser.setSweepState(0, "Start")
                del self.avgs
                self.avgs = []
                self.measTimer.start()

            self.statusbar.showMessage(f"Sweep conditions updated")

    def OnCenterSpanChanged(self):
        if not self.recalc:
            self.recalc = True
            
            was_sweeping = self.sweeping
            if was_sweeping:
                self.measTimer.stop()
                self.laser.setSweepState(0, "Stop")
            
            sender = self.sender()
            if (sender == self.centerSpin):
                if self.centerSpin.value() > self.maxCenter: self.centerSpin.setValue(self.maxCenter)
                if self.centerSpin.value() < self.minCenter: self.centerSpin.setValue(self.minCenter)
                if self.centerSpin.value() - self.spanSpin.value()/2.0 < self.minWl:
                    self.spanSpin.setValue((self.centerSpin.value() - self.minWl)*2.0)
                if self.centerSpin.value() + self.spanSpin.value()/2.0 > self.maxWl:
                    self.spanSpin.setValue((self.maxWl - self.centerSpin.value())*2.0)
            
            elif (sender == self.spanSpin):
                if self.spanSpin.value() > self.maxSpan: self.spanSpin.setValue(self.maxSpan)
                if self.spanSpin.value() < self.minSpan: self.spanSpin.setValue(self.minSpan)
                if self.centerSpin.value() - self.spanSpin.value()/2.0 < self.minWl:
                    self.centerSpin.setValue(self.minWl + self.spanSpin.value()/2.0)
                if self.centerSpin.value() + self.spanSpin.value()/2.0 > self.maxWl:
                    self.centerSpin.setValue(self.maxWl - self.spanSpin.value()/2.0)
                        
            self.startSpin.setValue(self.centerSpin.value() - self.spanSpin.value()/2.0)
            self.stopSpin.setValue(self.centerSpin.value() + self.spanSpin.value()/2.0)

            self.startfSpin.setValue(self.c/self.stopSpin.value())
            self.stopfSpin.setValue(self.c/self.startSpin.value())
            self.centerfSpin.setValue(self.c/self.centerSpin.value())
            self.spanfSpin.setValue(self.stopfSpin.value() - self.startfSpin.value())

            self.recalc = False
            if was_sweeping:
                sw_start = self.startSpin.value()
                sw_stop = self.stopSpin.value()
                sw_speed = self.speedSpin.value()
                sw_time = (sw_stop - sw_start)/sw_speed
                time_range = 1.1*sw_time
                time_delay = sw_time/10.0
                self.laser.setSweep(0, 'CONT', sw_start, sw_stop, 1, 0, 0, sw_speed)
                self.osc.SetTimeRange(time_range)
                self.osc.SetTimeDelay(time_delay)
                self.laser.setSweepState(0, "Start")
                del self.avgs
                self.avgs = []
                self.measTimer.start()

            self.statusbar.showMessage(f"Sweep conditions updated")

    def OnFreqChanged(self):
        if not self.frecalc and not self.recalc:
            self.frecalc = True        
            sender = self.sender()
            if (sender == self.startfSpin):
                self.startSpin.setValue(self.c/sender.value())  
            elif (sender == self.stopfSpin):
                self.stopSpin.setValue(self.c/sender.value())  
            elif (sender == self.centerfSpin):
                self.centerSpin.setValue(self.c/sender.value())
            elif (sender == self.spanfSpin):
                startwl = self.c/(self.centerfSpin.value() + self.spanfSpin.value()/2.0)
                stopwl = self.c/(self.centerfSpin.value() - self.spanfSpin.value()/2.0)
                self.spanSpin.setValue(stopwl - startwl)

            self.frecalc = False

    def OnSpeedChanged(self):    
        if self.sweeping:
            self.measTimer.stop()
            self.laser.setSweepState(0, "Stop")

            sw_start = self.startSpin.value()
            sw_stop = self.stopSpin.value()
            sw_speed = self.speedSpin.value()
            sw_time = (sw_stop - sw_start)/sw_speed
            time_range = 1.1*sw_time
            time_delay = sw_time/10.0

            self.laser.setSweep(0, 'CONT', sw_start, sw_stop, 1, 0, 0, sw_speed)
            self.osc.SetTimeRange(time_range)
            self.osc.SetTimeDelay(time_delay)
            self.laser.setSweepState(0, "Start")
            del self.avgs
            self.avgs = []
            self.measTimer.start()

            self.statusbar.showMessage(f"Sweep conditions updated")

    def OnPowerChanged(self):        
        was_sweeping = self.sweeping
        if was_sweeping:
            self.measTimer.stop()
            self.laser.setSweepState(0, "Stop")

        if self.inited:
            self.laser.setPwr(0, self.powerSpin.value())

        if was_sweeping:
            self.laser.setSweepState(0, "Start")
            del self.avgs
            self.avgs = []
            self.measTimer.start()

        self.statusbar.showMessage(f"Sweep conditions updated")

    def OnOscYChanged(self):
        was_sweeping = self.sweeping
        if was_sweeping:
            self.measTimer.stop()

        if self.inited:
            chan = self.oscchanSpin.value()
            self.osc.SetProbe(1, chan)
            self.osc.SetCoupling(chan, self.couplingCombo.currentText())
            self.osc.SetRange(self.rangeSpin.value(), chan)
            self.osc.SetOffset(self.offsetSpin.value(), chan)

        if was_sweeping:
                self.measTimer.start()

        self.statusbar.showMessage(f"Vertical scale updated")

    def OnTriggerChanged(self):
        was_sweeping = self.sweeping
        if was_sweeping:
            self.measTimer.stop()

        if self.inited:
            self.osc.SetTriggerSource(self.triggerCombo.currentText())
            self.osc.SetTriggerLevel(self.triglvSpin.value())

        if was_sweeping:
                self.measTimer.start()

        self.statusbar.showMessage(f"Trigger updated")

    def OnAcquisitionChanged(self):
        was_sweeping = self.sweeping
        if was_sweeping:
            self.measTimer.stop()

        if self.inited:
            self.osc.SetAcqType(self.acqCombo.currentText())

        if was_sweeping:
            del self.avgs
            self.avgs = []
            self.measTimer.start()

        self.statusbar.showMessage(f"Acquisition type updated")
            
    def OnChangeYScale(self):
        if self.voltRadio.isChecked():
            self.y_results = self.volts
        elif self.linRadio.isChecked():
            self.y_results = self.mW
        elif self.dbRadio.isChecked():
            self.y_results = self.dbm
        self.RescaleY()
        self.UpdateGraph()
        self.statusbar.showMessage(f"Y Scale changed")

    def OnChangeXScale(self):
        if self.nmRadio.isChecked():
            self.x_results = self.wls
            self.xscaleStack.setCurrentIndex(0)
        elif self.thzRadio.isChecked():
            self.x_results = self.freqs
            self.xscaleStack.setCurrentIndex(1)
        self.RescaleX()        
        self.UpdateGraph()
        self.statusbar.showMessage(f"X Scale changed")
        
    def OnSaveSettings(self):
        file = QFileDialog.getSaveFileName(self, "Save settings", self.lastdir, "json files (*.json)")
        filename = file[0]
        
        lastslash = filename.rfind("/")
        self.lastdir = filename[:lastslash + 1]
       
        self.saveSettings(filename)
        
        self.statusbar.showMessage(f"Settings saved")
    
    def OnLoadSettings(self):
        file = QFileDialog.getOpenFileName(self, "Load settings", self.lastdir, "json files (*.json)")
        filename = file[0]
        
        lastslash = filename.rfind("/")
        self.lastdir = filename[:lastslash + 1]
        
        self.loadSettings(filename)
        
        self.statusbar.showMessage(f"Settings loaded")
    
    def OnSaveResults(self):
        file = QFileDialog.getSaveFileName(self, "Save results", self.lastdir, "Data files (*.txt *.csv *.dat)")
        filename = file[0]
        
        lastslash = filename.rfind("/")
        self.lastdir = filename[:lastslash + 1]
       
        if filename[-4:] == ".csv":
            with open(filename, 'w') as f:
                f.write("Wavelength (nm),Power (mW),Power (dBm)\n")
                for i in range(len(self.x_results)):
                    f.write(f"{self.x_results[i]:.3f},{self.y_results[i]:.6f}\n")
                f.close()
                self.statusbar.showMessage(f"Results saved")
        elif len(filename) > 0:
            with open(filename, 'w') as f:
                f.write("Wavelength (nm),Power (mW),Power (dBm)\n")
                for i in range(len(self.x_results)):
                    f.write(f"{self.x_results[i]:.3f},{self.y_results[i]:.6f}\n")
                f.close()
                self.statusbar.showMessage(f"Results saved")

    def saveSettings(self, filename=""):
        if filename == "":
            filename = self.settingsfile    
        settings_dict = {}
        settings_dict["__lastdir__"] = self.lastdir
        for w in self.findChildren(QSpinBox):
            settings_dict[w.objectName()] = w.value()
        for w in self.findChildren(QDoubleSpinBox):
            settings_dict[w.objectName()] = w.value()
        for w in self.findChildren(QCheckBox):
            settings_dict[w.objectName()] = w.isChecked()
        for w in self.findChildren(QRadioButton):
            settings_dict[w.objectName()] = w.isChecked()
        for w in self.findChildren(QComboBox):
            settings_dict[w.objectName()] = w.currentIndex()
            
        json.dump(settings_dict, open(filename, "w"))
        
    def loadSettings(self, filename=""):
        if filename == "":
            filename = self.settingsfile
        lastslash = self.fullpath.rfind("/")
        path = self.fullpath[:lastslash + 1] + filename

        if os.path.isfile(path):
            settings_dict = json.load(open(path, "r"))
            if "__lastdir__" in settings_dict:
                self.lastdir = settings_dict["__lastdir__"]
                for key in settings_dict:
                    if key[:2] != "__" and key[-2:] != "__":
                        try:
                            w = self.findChild(QWidget, key)
                            if "Spin" in key:
                                w.setValue(settings_dict[key])
                            if "Check" in key:
                                w.setChecked(settings_dict[key])
                            if "Radio" in key:
                                w.setChecked(settings_dict[key])
                            if "Combo" in key:
                                w.setCurrentIndex(settings_dict[key])
                        except:
                            pass

    def Exit(self):
        quit()

    def About(self):
        QMessageBox.about(self, "About", "This software was created for the LCO HomeMade® " +
                          "Brillouin Optical Spectrum Analyzer: HM-BOSA.\n\n" +
                          "It depends on the following python packages:\n" +
                          "\t- PyQt5\n" +
                          "\t- Numpy\n" +
                          "\t- Matplotlib\n" +
                          "\t- Pyvisa\n" +
                          "It also depends on our HomeMade® RemoteVisa Python package\n\n" +
                          "Created by Paulo F. Jarschel, 2022")
    
    def CloseDevices(self):
        self.statusbar.showMessage(f"Devices closed")

    def closeEvent(self, event):
        self.Stop()
        self.saveSettings()

#Run
if __name__ == "__main__":
    myappid = 'pfjarschel.pyinterfaces.lco-hmbosa.0.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    window = MainWindow()

    sys.exit(app.exec_())