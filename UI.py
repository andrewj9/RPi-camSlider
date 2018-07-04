import RPi.GPIO as GPIO
import time
from encoder import RotaryEncoder
from PIL import ImageFont, Image
from smbus import SMBus
from time import sleep
from lib_oled96 import ssd1306
from StepperControl import Stepper
from Fan import Fan
import threading
from threading import Lock

GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#Constructs the menu structure
class Interface(object):
	def __init__(self):
		self.i2cbus = SMBus(1)
		self.oled = ssd1306(self.i2cbus)
		self.font = ImageFont.truetype('/home/pi/Code/FreeSans.ttf', 10)
		self.font2 = ImageFont.truetype('/home/pi/Code/FreeSans.ttf', 11)
		self.font3 = ImageFont.truetype('/home/pi/Code/FreeSans.ttf', 18)
		self.font4 = ImageFont.truetype('/home/pi/Code/FreeSans.ttf', 36)
		self.disp = self.oled.canvas
		self.padding = 1
		self.top = self.padding
		self.bottom = self.oled.height - self.padding
		self.left = self.padding
		self.right = self.oled.width - self.padding
		self.line1 = 17
		self.line2 = 29
		self.line3 = 41
		self.line4 = 53
		self.lines = [self.line1, self.line2, self.line3, self.line4]
		self.column1 = self.left + 2
		self.column2 = self.left + 64
		self.column3 = self.right - 44
		self.selector = 0
		self.interfaces = []
		self.currentMenu = None
		self.b = None
		self.busy = False
		self.exit = False
		self.lock = Lock()
		self.stepsPerDeg = 1
		self.stepsPerUnit = 1
		self.motorStepTime = 0.01
		self.sequenceStartTime = 0
		self.timeStamp = 0
		self.lastRun = 0
		self.xEvent = threading.Event()
		self.rEvent = threading.Event()
		return

	#Define pin inputs and outputs
	def setControls(self, enter, go, LED, up, down):
		self.enterButt = enter
		self.goButt = go
		self.buttLED = LED
		#Button Indicator Settings
		self.buttLEDfreq = 1
		self.buttDuty = 25

		#Pin assignments
		GPIO.setup(self.buttLED, GPIO.OUT)
		GPIO.setup(self.goButt, GPIO.IN, pull_up_down = GPIO.PUD_UP)
		GPIO.setup(self.enterButt, GPIO.IN, pull_up_down = GPIO.PUD_UP)
		
		GPIO.add_event_detect(self.goButt, GPIO.FALLING, callback = self.goSTART, bouncetime = 500)
		GPIO.add_event_detect(self.enterButt, GPIO.FALLING, callback = self.selectButt, bouncetime = 500)
		self.encoder = RotaryEncoder(up,down,self.decode)
		self.buttON(True)
		time.sleep(0.125)
		self.buttON(False)
		time.sleep(0.125)
		self.buttON(True)
		time.sleep(0.125)
		self.buttON(False)
		return

	#Calibrate the Motors
	def homeMotors(self):
		self.fan(True)
		self.xMotor.calibrate()
		#self.rMotor.calibrate()
		self.fan(True)
		return

	#Define the fan pins
	def setFan(self, pin):
		self.blower = Fan(pin, 100, 0.25, 120)
		return

	#Define Camera Trigger Pins
	def setCamTrigger(self, half, full):
		self.halfPress = half
		self.fullPress = full
		GPIO.setup(self.halfPress, GPIO.OUT)
		GPIO.setup(self.fullPress, GPIO.OUT)
		GPIO.output(self.halfPress, True)
		GPIO.output(self.fullPress, True)
		return

	#Turn the button LED on or off (Button)
	def buttON(self, val):
		GPIO.output(self.buttLED, val)
		return

	#Create menu items
	def populate(self):
		self.main = Menu('Main Menu')

		self.ready = Go('Capture')
		self.preview = Go('Preview')
		self.movement = Menu('Movement')
		self.displacement = Menu('Displacement')
		self.time = Menu('Time')
		self.drive = Menu('Drive')
		
		self.translation = Menu('Translation')
		self.rotation = Menu('Rotation')
		self.initPos = Menu('Initial Positions')
		self.travDir = Menu('Travel Directions')

		self.camera = Menu('Camera')

		self.calibrate = Menu('Calibrate')
		self.manualControl = Menu('Manual Control')

		self.freeMove = Action('User Control X')
		self.freeRotate = Action('User Control R')

		self.totalDisp = Option('Total Displace')
		self.incDisp = Option('Increment')

		self.totalRot = Option('Total Rotation')
		self.incRot = Option('Increment')

		self.initX = Option('Initial X-Position')
		self.initR = Option('Initial R-Position')

		self.travX = Option('Initial X-Direction')
		self.travR = Option('Initial R-Direction')

		self.tVal = Camera('Time Value')            # Shutter speed of camera
		self.nomages = Option('Images')             # Number of images to capture

		self.inter = Option('Interval')             # Interval between shots in seconds
		self.totalTime = Option('Total Time')       # Total time of sequence in minutes

		self.calTrans = Action('Translation')
		self.calRot = Action('Rotation')

		self.hold = Option('Holding Power')

		self.main.setItems(self.ready, self.movement, self.time, self.drive)
		self.main.pageInfo = 'Today'

		self.movement.setItems(self.displacement, self.initPos, self.travDir, self.main)
		self.displacement.setItems(self.translation, self.rotation, self.movement)
		self.drive.setItems(self.calibrate, self.manualControl, self.hold, self.main)
		self.time.setItems(self.totalTime, self.inter, self.camera, self.main)
		self.manualControl.setItems(self.freeMove, self.freeRotate, self.drive)
		self.ready.setItems(self.preview, self.main)
		self.ready.setHardware(self.xMotor, self.rMotor)
		self.ready.setSubtitle('Shots')
		self.preview.setItems(self.ready, self.main)
		self.preview.setHardware(self.xMotor, self.rMotor)
		self.preview.setSubtitle('Preview')

		self.translation.setItems(self.totalDisp, self.incDisp, self.movement)
		self.initPos.setItems(self.initX, self.initR, self.movement)
		self.travDir.setItems(self.travX, self.travR, self.movement)
		self.rotation.setItems(self.totalRot, self.incRot, self.movement)
		self.camera.setItems(self.tVal, self.nomages, self.time)

		self.calibrate.setItems(self.calTrans, self.calRot, self.drive)
		self.freeMove.setItems(self.manualControl)
		self.freeMove.setHardware(self.xMotor)
		self.freeRotate.setItems(self.manualControl)
		self.freeRotate.setHardware(self.rMotor)
		self.hold.setItems(self.drive)
		self.hold.hasRange(True)
		self.hold.setRange(0,2)
		self.hold.hasAlternate(True)
		self.hold.setAlternate('OFF', 'LOW', 'HIGH')
		self.hold.setVal(1)

		self.totalDisp.setItems(self.translation)
		self.totalDisp.canZero(True)
		self.totalDisp.setVal(10000)
		self.totalDisp.setMultiplier(100)
		self.incDisp.setItems(self.translation)
		self.incDisp.canZero(True)
		self.incDisp.setVal(1)

		self.totalRot.setItems(self.rotation)
		self.totalRot.canZero(True)
		self.totalRot.setVal(90)
		self.incRot.setItems(self.rotation)
		self.incRot.canZero(True)
		self.incRot.setVal(1)

		self.totalTime.setItems(self.time)
		self.totalTime.setVal(45)
		self.inter.setItems(self.time)
		self.inter.setVal(2)

		self.tVal.setItems(self.camera)
		self.tVal.setVal(0)
		self.nomages.setItems(self.camera)
		self.nomages.setVal(10)

		self.calTrans.setItems(self.calibrate)
		self.calTrans.setHardware(self.xMotor)
		self.calRot.setItems(self.calibrate)
		self.calRot.setHardware(self.rMotor)

		self.travX.setItems(self.travDir)
		self.travX.hasRange(True)
		self.travX.setRange(0,1)
		self.travX.hasAlternate(True)
		self.travX.setAlternate('FWD', 'REV')
		self.travR.setItems(self.travDir)
		self.travR.hasRange(True)
		self.travR.setRange(0,1)
		self.travR.hasAlternate(True)
		self.travR.setAlternate('FWD', 'REV')

		self.initX.setItems(self.initPos)
		self.initX.hasRange(True)
		self.initX.setRange(self.xMotor.Limits[0], self.xMotor.Limits[1])
		self.initX.setMultiplier(100)
		self.initR.setItems(self.initPos)
		self.initR.hasRange(True)
		self.initR.setRange(self.rMotor.Limits[0], self.rMotor.Limits[1])
		self.initR.setMultiplier(100)

		self.currentMenu = self.main
		return

	#Turn the fan on or off (Boolean)
	def fan(self, isOn):
		if self.hold.getVal() == 2:
			self.blower.on()
		elif isOn:
			self.blower.on()
		elif ~isOn:
			self.blower.off()
		return

	#Define pins and create translation motor object
	def setTransMotor(self, pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, endButt, steps):
		self.xMotor = Stepper(pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, endButt)
		self.xMotor.invert()
		self.xMotor.pwmHoldSet(1)
		self.stepsPerUnit = steps
		return

	#Define pins and create rotation motor object
	def setRotMotor(self, pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, endButt, steps):
		self.rMotor = Stepper(pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, endButt)
		self.stepsPerDeg = steps
		return

	#Set hard limits of displacement motor
	def setTransLimits(self, min, max):
		self.xMotor.setLimits(min, max)
		return

	#Set hard limits of rotational motor
	def setRotLimits(self, min, max):
		self.rMotor.setLimits(min, max)
		return

	#Update values of current menu
	def updateInfo(self, val):
		if type(self.currentMenu) is Option or type(self.currentMenu) is Camera:
			self.currentMenu.setVal(val)
			self.disp.text((self.column3, self.top), str(self.currentMenu.toString()[2]), font = self.font, fill = 0)
			self.disp.text((self.column3, self.top), str(self.currentMenu.toString()[1]), font = self.font, fill = 1)
		if type(self.currentMenu) is Action or type(self.currentMenu) is Go:
			self.currentMenu.setVal(val)
		return

	#Draw objects of the current menu
	def draw(self):
		self.disp.text((1, self.top), self.currentMenu.title, font = self.font, fill = 1)
		#Populate the interface list with the current menu's items
		try:
			self.interfaces = self.currentMenu.getItems()
		except:
			print('Menu population error')
		
		if type(self.currentMenu) is Menu:
			self.updateInfo(self.toString())
			for item in self.interfaces:
				if item != None:
					self.disp.text((self.column1, self.lines[self.interfaces.index(item)]), self.interfaces[self.interfaces.index(item)].title, font = self.font2, fill = 1)
					if self.interfaces[self.interfaces.index(item)].getVal() != None:
						self.disp.text((self.column3, self.lines[self.interfaces.index(item)]), self.interfaces[self.interfaces.index(item)].toString()[2], font = self.font2, fill = 0)
						self.disp.text((self.column3, self.lines[self.interfaces.index(item)]), self.interfaces[self.interfaces.index(item)].toString()[1], font = self.font2, fill = 1)
		#Display scheme for camera shutter speed selection menu
		if type(self.currentMenu) is Option or type(self.currentMenu) is Camera:
			#Erase the previous display and write the new display
			self.disp.text((self.column1, self.lines[1]), self.currentMenu.toString()[2], font = self.font4, fill = 0)
			self.disp.text((self.column1, self.lines[1]), self.currentMenu.toString()[1], font = self.font4, fill = 1)
		#Display scheme for Action menus
		if type(self.currentMenu) is Action:
			#Display info about the current menu functionality
			self.disp.text((self.column1, self.lines[0]), self.currentMenu.getSubtitle(), font = self.font2, fill = 1)
			#Erase the previous display and write the new display
			self.disp.text((self.column1, self.lines[2]), self.currentMenu.toString()[2], font = self.font3, fill = 0)
			self.disp.text((self.column1, self.lines[2]), self.currentMenu.toString()[1], font = self.font3, fill = 1)
			#Display the 'Position' heading
			self.disp.text((self.column2, self.lines[0]), 'Position', font = self.font2, fill = 1)
			#Erase the previous display and write the new display
			self.disp.text((self.column2, self.lines[2]), str(self.currentMenu.getPosition()[1]), font = self.font3, fill = 0)
			self.disp.text((self.column2, self.lines[2]), str(self.currentMenu.getPosition()[0]), font = self.font3, fill = 1)
		#Display scheme for Capture menu
		if type(self.currentMenu) is Go:
			#self.updateInfo(self.currentMenu.getVal())
			self.currentMenu.updatePosition()
			#Display 'Shots Remaining' tag
			self.disp.text((self.column1, self.lines[0]), self.currentMenu.getSubtitle(), font = self.font2, fill = 1)
			#Display 'Time Remaining'
			self.disp.text((self.column2, self.top), self.currentMenu.getTimeString()[1], font = self.font2, fill = 0)
			self.disp.text((self.column2, self.top), self.currentMenu.getTimeString()[0], font = self.font2, fill = 1)
			#Erase the previous display and write the new display (Shots Remaining)
			self.disp.text((self.column1, self.lines[2]), self.currentMenu.toString()[2], font = self.font3, fill = 0)
			self.disp.text((self.column1, self.lines[2]), self.currentMenu.toString()[1], font = self.font3, fill = 1)
			#Display the 'Position' heading
			self.disp.text((self.column2, self.lines[0]), 'Position', font = self.font2, fill = 1)
			#Erase the previous display and write the new display (xMotor)
			self.disp.text((self.column2, self.lines[1]), 'X: ' + str(self.currentMenu.getPosition(0)[1]), font = self.font2, fill = 0)
			self.disp.text((self.column2, self.lines[1]), 'X: ' + str(self.currentMenu.getPosition(0)[0]), font = self.font2, fill = 1)
			#Erase the previous display and write the new display (rMotor)
			self.disp.text((self.column2, self.lines[2]), 'R: ' + str(self.currentMenu.getPosition(1)[1]), font = self.font2, fill = 0)
			self.disp.text((self.column2, self.lines[2]), 'R: ' + str(self.currentMenu.getPosition(1)[0]), font = self.font2, fill = 1)
		return

	#Hightlight the menu option indicated by the selector
	def highlight(self):
		if type(self.currentMenu) is Menu:
			try:
				textDim = self.font.getsize(str(self.interfaces[self.selector]))
				self.disp.rectangle((self.left, self.lines[self.selector] - 1, self.left + textDim[0] + 5, self.lines[self.selector] + textDim[1] + 2), outline = 0, fill = 1)
				self.disp.text((self.column1, self.lines[self.selector]), self.interfaces[self.selector].toString()[0], font = self.font2, fill = 0)
				if self.interfaces[self.selector].getVal() != None:
					self.disp.text((self.column3, self.lines[self.selector]), self.interfaces[self.selector].toString()[1], font = self.font2, fill = 0)
			except:
				pass
		return

	#Redraw the current menu
	def update(self):
		self.oled.cls()
		self.draw()
		self.highlight()
		self.oled.display()
		return

	#Refresh the display without clearing previous values
	def refresh(self):
		self.draw()
		self.oled.display()
		return

	#Call the update method
	def getMenu(self):
		self.update()
		return

	#Black out the display
	def off(self):
		self.oled.cls()
		self.fan(False)
		self.buttON(False)
		self.xMotor.OFF()
		self.rMotor.OFF()
		return

	#Return object info
	def toString(self):
		return self.currentMenu.toString()

	#Set an object value
	def setVal(self, val):
		self.currentMenu.setVal(val)
		return

	#Get an object value
	def getVal(self):
		return self.currentMenu.getVal()

	#Save option values to file
	def saveDATA(self):
		data = [self.totalDisp.getVal(), self.incDisp.getVal(), self.totalRot.getVal(), self.incRot.getVal(), self.tVal.getVal(), self.nomages.getVal(), self.inter.getVal(), self.totalTime.getVal(), self.xMotor.getPosition(), self.rMotor.getPosition()]
		file = open("//home//pi//Control//settings.txt", "w")

		for i in range(0, data.__len__()):
			file.write(str(data[i]))
			file.write(',')

		file.close()
		return

	#Load saved option values from file
	def loadDATA(self):
		try:
			file = open("//home//pi//Control//settings.txt", "r")
			data = file.readlines()
			file.close()

			for line in data:
				vals = line.split(',')
			print(data)

			self.totalDisp.setVal(vals[0])
			self.incDisp.setVal(vals[1])
			self.totalRot.setVal(vals[2])
			self.incRot.setVal(vals[3])
			self.tVal.setVal(vals[4])
			self.nomages.setVal(vals[5])
			self.inter.setVal(vals[6])
			self.totalTime.setVal(vals[7])
			self.xMotor.setPosition(vals[8])
			self.rMotor.setPosition(vals[9])

		except:
			print("Load failed")
		return

	#Select the menu represented by the selector value
	def selectButt(self, channel):
		self.buttON(False)
		self.fan(False)
		try:
			self.currentMenu.isRecent(True)
		except:
			pass
		self.currentMenu = self.interfaces[self.selector]
		if type(self.currentMenu) is Action or type(self.currentMenu) is Go:
			self.buttON(True)
		if type(self.currentMenu) is Action:
			self.fan(True)
		self.selector = 0		
		self.calculate()
		self.update()
		self.saveDATA()
		return

	#Increase the menu selector one increment
	def nextButt(self, channel):
		if self.selector < self.interfaces.__len__() - 1:
			self.selector += 1
		else:
			self.selector = 0
		self.update()
		return

	#Decrease the menu selector one increment
	def prevButt(self, channel):
		if self.selector > 0:
			self.selector -= 1
		else:
			self.selector = self.interfaces.__len__() - 1
		self.update()
		return

	#Update all option values to agree with the most recent user setting	
	def calculate(self):
		if self.incDisp.isMostRecent() or self.nomages.isMostRecent():
			self.totalDisp.setVal(self.incDisp.getVal() * self.nomages.getVal())
			self.incDisp.isRecent(False)
			self.nomages.isRecent(False)

		if self.totalDisp.isMostRecent() or self.nomages.isMostRecent():
			self.incDisp.setVal(self.totalDisp.getVal() / self.nomages.getVal())
			self.totalDisp.isRecent(False)
			self.nomages.isRecent(False)

		if self.incRot.isMostRecent() or self.nomages.isMostRecent():
			self.totalRot.setVal(self.incRot.getVal() * self.nomages.getVal())
			self.incRot.isRecent(False)
			self.nomages.isRecent(False)

		if self.totalRot.isMostRecent() or self.nomages.isMostRecent():
			self.incRot.setVal(self.totalRot.getVal() / self.nomages.getVal())
			self.totalRot.isRecent(False)
			self.nomages.isRecent(False)

		if self.totalTime.isMostRecent() or self.inter.isMostRecent():
			self.nomages.setVal((self.totalTime.getVal() * 60) / self.inter.getVal())
			self.totalDisp.setVal(self.nomages.getVal() * self.incDisp.getVal())
			self.totalRot.setVal(self.nomages.getVal() * self.incRot.getVal())
			self.inter.isRecent(False)
			self.totalTime.isRecent(False)

		if self.inter.isMostRecent() or self.nomages.isMostRecent():
			self.totalTime.setVal((self.inter.getVal() * self.nomages.getVal()) / 60.0)
			self.totalDisp.setVal(self.nomages.getVal() * self.incDisp.getVal())
			self.totalRot.setVal(self.nomages.getVal() * self.incRot.getVal())
			self.inter.isRecent(False)
			self.nomages.isRecent(False)

		if self.totalTime.isMostRecent() or self.nomages.isMostRecent():
			self.inter.setVal((self.totalTime.getVal() * 60) / self.nomages.getVal())
			self.totalTime.isRecent(False)
			self.nomages.isRecent(False)

		if (self.inter.getVal() - self.tVal.getShutter() - self.motorStepTime * self.stepsPerUnit * self.incDisp.getVal()) < -1:
			palm = self.inter.getVal() - self.tVal.getShutter() - self.motorStepTime * self.stepsPerUnit * self.incDisp.getVal()
			face = self.inter.getVal()
			self.inter.setVal(face - palm)
			self.inter.increment(1)
			print("Interval Updated")

		if (self.inter.getVal() - self.tVal.getShutter() - self.motorStepTime * self.stepsPerUnit * self.incDisp.getVal()) < 0:
			self.inter.increment(1)
			print("Interval Updated")

		self.xMotor.pwmHoldSet(self.hold.getVal())
		self.rMotor.pwmHoldSet(self.hold.getVal())
		return

	#Determine what value the encoder should increment
	def decode(self, event):
		with self.lock:
			if type(self.currentMenu) is Menu or type(self.currentMenu) is Go:
				if event == 1:
					self.nextButt(1)
				elif event == 2:
					self.prevButt(1)
			elif type(self.currentMenu) is Action or type(self.currentMenu) is Option or type(self.currentMenu) is Camera:
				if event == 1:
					encoderQueue = 1
					self.jog(0, encoderQueue)
				elif event == 2:
					encoderQueue = -1
					self.jog(0, encoderQueue)
		return

	#Increment some value with the encoder
	def jog(self, channel, val):
		if type(self.currentMenu) is Option or type(self.currentMenu) is Camera:
			self.currentMenu.increment(val)
			self.refresh()
		elif type(self.currentMenu) is Action:
			self.currentMenu.jog(val)
			self.refresh()
		return

	#Update the timestamp on the display
	def getTime(self):
		self.timeStamp = time.monotonic()
		hours = int((self.totalTime.getVal() - (self.timeStamp-self.sequenceStartTime)/60)/60)
		minutes = int((self.totalTime.getVal() - (self.timeStamp-self.sequenceStartTime)/60))
		seconds = int((self.totalTime.getVal() * 60 - (self.timeStamp-self.sequenceStartTime))%60)
		if hours < 10:
			hourString = '0' + str(hours)
		else:
			hourString = str(hours)
		if minutes < 10:
			minString = '0' + str(minutes)
		else:
			minString = str(minutes)
		if seconds < 10:
			secString = '0' + str(seconds)
		else:
			secString = str(seconds)
		timeString = hourString + ':' + minString + ':' + secString
		self.ready.setTimeString(timeString)
		self.refresh()
		return

	#Trigger what ever action is indicated by the current menu
	def goSTART(self, channel):
		if time.monotonic() - self.lastRun < 2:
			print('DoubleGo')
			return
		if ~self.busy:
			self.exit = False
			self.buttON(False)
			if self.currentMenu == self.preview:
				self.fan(True)
				self.busy = True
				self.xMotor.goTo(self.initX.getVal())
				self.rMotor.goTo(self.initR.getVal())
				self.refresh()
				sleep(1)
				if self.travX.getVal() == 0:
					self.xThread = stepperThread(1, "Trans-Thread", self.xEvent, self.totalDisp.getVal(), self.incDisp.getVal(), self.xMotor, True)
				elif self.travX.getVal() == 1:
					self.xThread = stepperThread(1, "Trans-Thread", self.xEvent, -self.totalDisp.getVal(), self.incDisp.getVal(), self.xMotor, True)
				if self.travR.getVal() == 0:
					self.rThread = stepperThread(2, "Rot-Thread", self.rEvent, self.totalRot.getVal(), self.incRot.getVal(), self.rMotor, True)
				elif self.travR.getVal() == 1:
					self.rThread = stepperThread(2, "Rot-Thread", self.rEvent, -self.totalRot.getVal(), self.incRot.getVal(), self.rMotor, True)
				self.xThread.start()
				self.rThread.start()
				while self.xThread.is_alive() or self.rThread.is_alive():
					self.refresh()
					sleep(0.01)
				self.buttON(True)
				self.fan(True)
				self.currentMenu.setVal(self.nomages.getVal())
				self.refresh()
				self.busy = False
				self.xMotor.goTo(self.initX.getVal())
				self.rMotor.goTo(self.initR.getVal())
				self.lastRun = time.monotonic()

			elif self.currentMenu == self.ready:
				self.fan(True)
				self.busy = True
				self.xMotor.goTo(self.initX.getVal())
				self.rMotor.goTo(self.initR.getVal())
				self.refresh()
				GPIO.output(self.halfPress, False)
				sleep(1)
				if self.travX.getVal() == 0:
					self.xThread = stepperThread(1, "Trans-Thread", self.xEvent, self.totalDisp.getVal(), self.incDisp.getVal(), self.xMotor, False)
				elif self.travX.getVal() == 1:
					self.xThread = stepperThread(1, "Trans-Thread", self.xEvent, -self.totalDisp.getVal(), self.incDisp.getVal(), self.xMotor, False)
				if self.travR.getVal() == 0:
					self.rThread = stepperThread(2, "Rot-Thread", self.rEvent, self.totalRot.getVal(), self.incRot.getVal(), self.rMotor, False)
				elif self.travR.getVal() == 1:
					self.rThread = stepperThread(2, "Rot-Thread", self.rEvent, -self.totalRot.getVal(), self.incRot.getVal(), self.rMotor, False)
				self.sequenceStartTime = time.monotonic()
				self.xThread.start()
				self.rThread.start()
				n = 0   #Shot counter for UI display
				while self.xThread.is_alive() or self.rThread.is_alive():
					t1 = time.monotonic()
					n += 1
					self.captureSequence(n)
					self.xEvent.set()
					self.rEvent.set()
					self.refresh()
					self.timeStamp = time.monotonic()
					self.monotomiTimer(t1, self.inter.getVal())
				self.buttON(True)
				self.fan(False)
				self.currentMenu.setVal(self.nomages.getVal())
				self.refresh()
				self.busy = False
				self.xMotor.goTo(self.initX.getVal())
				self.rMotor.goTo(self.initR.getVal())
				self.lastRun = time.monotonic()

			elif self.currentMenu == self.calTrans:
				self.fan(True)
				self.buttON(False)
				self.xMotor.calibrate()
				self.buttON(True)
				self.update()
				self.fan(False)				

			elif self.currentMenu == self.calRot:
				self.fan(True)
				self.buttON(False)
				self.rMotor.calibrate()
				self.buttON(True)
				self.update()
				self.fan(False)

			elif self.currentMenu == self.freeMove:
				self.buttON(False)
				self.xMotor.goTo(self.currentMenu.getVal())
				self.buttON(True)
				self.update()

			elif self.currentMenu == self.freeRotate:
				self.buttON(False)
				self.rMotor.goTo(self.currentMenu.getVal())
				self.buttON(True)
				self.update()

			else:
				try:
					self.currentMenu.isRecent(True)
				except:
					pass
				self.currentMenu = self.ready
				self.buttON(True)
				self.fan(False)
				self.selector = 0
				self.calculate()
				self.update()
				self.saveDATA()
		else:
			self.exit = True
		return

	#Execute camera capture and update
	def captureSequence(self, shotNumber):
		self.buttON(True)
		self.capture(self.tVal.getShutter())
		self.buttON(False)
		self.updateInfo(self.nomages.getVal() - shotNumber)
		self.refresh()
		return

	#Trigger the camera
	def capture(self, time):
		GPIO.output(self.fullPress, False)
		sleep(time)
		GPIO.output(self.fullPress, True)
		GPIO.output(self.halfPress, True)
		return

	#Time for capture sequence
	def monotomiTimer(self, t1, delay):
		while time.monotonic() - t1 < delay:
			if time.monotonic() - t1 > self.inter.getVal() - 1:
				GPIO.output(self.halfPress, False)
			self.getTime()
			sleep(0.001)
		return

#For Display of options
class Menu(Interface):
	def __init__(self, title):
		self.title = title
		self.items = []
		return

	#Get the value
	def getVal(self):
		return

	#Set the value
	def setVal(self, val):
		return

	#Get list of items
	def getItems(self):
		return self.items

	#Set list of items
	def setItems(self, item1 = None, item2 = None, item3 = None, item4 = None):
		if item1 != None and item2 != None and item3 != None and item4 != None:
			self.items = [item1, item2, item3, item4]
		elif item1 != None and item2 != None and item3 != None:
			self.items = [item1, item2, item3]
		elif item1 != None and item2 != None:
			self.items = [item1, item2]
		elif item1 != None:
			self.items = [item1]
		return

	#Return object info
	def toString(self):
		return [self.title]

#For Interface with adjustable value
class Option(Interface):
	def __init__(self, title):
		self.title = title
		self.items = []
		self.range = [0,0]
		self.value = 0
		self.alternate = []
		self.previous = self.value
		self.mostRecent = False
		self.zeroable = False
		self.rangeable = False
		self.displayAlternate = False
		self.multiplier = 1
		return

	#Set the value
	def setVal(self, val):
		if self.rangeable:
			if int(val) >= self.range[0] and int(val) <= self.range[1]:
				self.previous = self.value
				self.value = int(val)
		elif self.zeroable:
			if int(val) >= 0:
				self.previous = self.value
				self.value = int(val)
			else:
				self.value = 0
		else:
			if int(val) > 0:
				self.previous = self.value
				self.value = int(val)
			else:
				self.value = 1
		return

	#Return the value
	def getVal(self):
		if self.hasAlternate == True:
			return self.alternate[self.value]
		else:
			return self.value

	#Set the range of values
	def setRange(self, min, max):
		if min < max:
			self.range = [min, max]
		return

	#Return the range of valid values
	def getRange(self):
		return self.range

	#Set the value multiplier
	def setMultiplier(self, val):
		self.multiplier = val
		return

	#Select if there is an alternate display
	def hasAlternate(self, val):
		self.displayAlternate = val
		return

	#Set the alternative display options
	def setAlternate(self, *args):
		self.alternate = args
		return

	#Increment the value
	def increment(self, inc):
		direction = inc*self.multiplier
		if self.rangeable:
			if self.value + direction >= self.range[0] and self.value + direction <= self.range[1]:
				self.previous = self.value
				self.value = int(self.value + direction)
		elif self.zeroable:
			if self.value + direction >= 0:
				self.previous = self.value
				self.value = int(self.value + direction)
		else:
			if self.value + direction > 0:
				self.previous = self.value
				self.value = int(self.value + direction)
		return

	#Return previous value
	def getPrevious(self):
		return self.previous

	#Get list of items
	def getItems(self):
		return self.items

	#Set list of items
	def setItems(self, item1 = None):
		self.items = [item1]
		return

	#Return object info
	def toString(self):
		if self.displayAlternate == True:
			return [self.title, str(self.alternate[self.getVal()]), str(self.alternate[self.getPrevious()])]
		else:
			return [self.title, str(self.getVal()), str(self.getPrevious())]

	#Return if it is most recent
	def isMostRecent(self):
		return self.mostRecent

	#Set most recent
	def isRecent(self, mostRecent):
		self.mostRecent = mostRecent
		return

	#Set if value can go to zero
	def canZero(self, boolean):
		self.zeroable= boolean
		return

	#Set if the value has a valid range
	def hasRange(self, boolean):
		self.rangeable = boolean
		return

#For Interface with movement control
class Action(Interface):
	def __init__(self, title):
		self.title = title
		self.subtitle = ''
		self.value = 0
		self.posNow = ''
		self.posPre = self.posNow
		self.previous = self.value
		self.hardware = None
		self.multiplier = 100
		return

	#Get the value
	def getVal(self):
		return self.value

	#Set the value
	def setVal(self, val):
		if val >= self.hardware.Limits[0] and val <= self.hardware.Limits[1]:
			try:
				self.previous = self.value
				self.value = int(val)
				self.hardware.goTo(self.value)
			except:
				print("Could not go")
		return

	#Set the subtitle
	def setSubtitle(self, name):
		self.subtitle = name
		return

	#Return the subtitle
	def getSubtitle(self):
		return self.subtitle

	#Jog the value
	def jog(self, val):
		if self.value + val*self.multiplier >= self.hardware.Limits[0] and self.value + val*self.multiplier <= self.hardware.Limits[1]:
			self.previous = self.value
			self.value += int(val*self.multiplier)
		return

	#Define the hardware
	def setHardware(self, hardware):
		self.hardware = hardware
		return

	#Return the step value of the hardware (int)
	def getPosition(self):
		if self.posNow != self.hardware.getPosition():
			self.posPre = self.posNow
			self.posNow = self.hardware.getPosition()
		return [self.posNow, self.posPre]

	#Get list of items
	def getItems(self):
		return self.items

	#Get the limits of the motor
	def getLimits(self):
		return [self.hardware.Limits[0], self.hardware.Limits[1]]

	#Set list of items
	def setItems(self, item = None):
		self.items = [item]
		return

	#Return object info
	def toString(self):
		return [self.title, str(self.value), str(self.previous)]

#For Interface with movement control
class Go(Interface):
	def __init__(self, title):
		self.title = title
		self.subtitle = ''
		self.value = 0
		self.items = []
		self.posNow = []
		self.posPre = []
		self.timer = ['00:00:00', '00:00:00']
		self.previous = self.value
		self.hardware = []
		return

	#Get the value
	def getVal(self):
		return self.value

	#Set the value
	def setVal(self, val):
		self.previous = self.value
		self.value = int(val)
		return

	#Set the subtitle
	def setSubtitle(self, name):
		self.subtitle = name
		return

	#Return the subtitle
	def getSubtitle(self):
		return self.subtitle

	#Set Time Remaining
	def setTimeString(self, timer):
		self.timer[1] = self.timer[0]
		self.timer[0] = timer
		return

	#Get Time Remaining
	def getTimeString(self):
		return self.timer

	#Define the hardware
	def setHardware(self, hardware0 = None, hardware1 = None):
		self.hardware = [hardware0, hardware1]
		self.posNow = [self.hardware[0].getPosition(), self.hardware[1].getPosition()]
		self.posPre = [0, 0]
		return

	#Update the position values
	def updatePosition(self):
		self.posPre[0] = self.posNow[0]
		self.posPre[1] = self.posNow[1]
		self.posNow[0] = self.hardware[0].getPosition()
		self.posNow[1] = self.hardware[1].getPosition()
		return

	#Return the step value of the hardware (int)
	def getPosition(self, slot):
		return [self.posNow[slot], self.posPre[slot]]

	#Get list of items
	def getItems(self):
		return self.items

	#Set list of items
	def setItems(self, Item1 = None, Item2 = None):
		self.items = [Item1, Item2]
		return

	#Return object info
	def toString(self):
		return [self.title, str(self.value), str(self.previous)]

# An interface class for setting the camera shutter speed
class Camera(Interface):
	def __init__(self, title):
		self.title = title
		self.value = 0
		self.previous = self.value
		self.mostRecent = False
		self.lock = Lock()
		self.shutter = [120.0, 90.0, 60.0, 45.0, 30.0, 20.0, 15.0, 10.0, 8.0, 5.0, 3.0, 2.0, 1.0, 0.5, 0.3333333, 0.25, 0.2, 0.1666666, 0.125, 0.1, 0.08333333, 0.06666666, 0.05, 0.04, 0.033333333, 0.02, 0.0125, 0.01]
		return

	#Increment the shutter speed selector value up or down
	def increment(self, direction):
		if self.value + direction < self.shutter.__len__() and self.value + direction >= 0:
			self.previous = self.value
			self.value += direction
		return

	#Return the decimal shutter speed for timing
	def getShutter(self):
		return self.shutter[self.value]

	#Get the value
	def getVal(self):
		return self.value

	#Set the value
	def setVal(self, val):
		if int(val) < self.shutter.__len__():
			self.value = int(val)
		return

	#Get list of items
	def getItems(self):
		return self.items

	#Set list of items
	def setItems(self, Item1 = None):
		self.items = [Item1]
		return

	#Return the fractional shutter speed for display
	def toString(self):
		with self.lock:
			try:
				if self.getShutter() < 1:
					if self.shutter[self.previous] < 1:
						return [self.title, "1/" + str(int(1/self.shutter[self.value])), "1/" + str(int(1/self.shutter[self.previous]))]
					else:
						return [self.title, "1/" + str(int(1/self.shutter[self.value])), str(self.shutter[self.previous])]
				else:
					if self.shutter[self.previous] < 1.0:
						return [self.title, str(int(self.shutter[self.value])),  "1/" + str(int(1/self.shutter[self.previous]))]
					else:
						return [self.title, str(int(self.shutter[self.value])), str(self.shutter[self.previous])]
			except:
				print('FuckFace')
				return [self.title, "69", "69"]

# This class is used to create a thread to control a stepper motor
class stepperThread(threading.Thread):
	def __init__(self, threadID, name, event, steps, increment, hardware, preview):
		threading.Thread.__init__(self)
		self.threadID = threadID
		self.name = name
		self.event = event
		self.steps = steps
		self.increment = increment
		self.hardware = hardware
		self.preview = preview
		
	def run(self):
		if self.preview:
			delay = 0.005
			self.hardware.clearSet = False
			self.event.set()
		elif self.increment < 100:
			delay = 0.005
			self.hardware.clearSet = True
			self.event.clear()
		elif math.fabs(val - self.getPosition()) < 1000 or self.holdDuty == self.highHoldDutyCycle:
			delay = 0.005
			self.hardware.clearSet = True
			self.event.clear()
		else:
			delay = 0.001
			self.hardware.clearSet = True
			self.event.clear()
		self.hardware.drive(self.name, self.event, self.steps, self.increment, delay)
		return

# This class is used to create locks
class LockedVariable(object):
	def __init__(self, value, lock=None):
		self._value = value
		self._lock = lock if lock else threading.RLock()
		self._locked = False

	@property
	def locked(self):
		return self._locked

	def assign(self, value):
		with self:
			self._value = value

	def release(self):
		self._locked = False
		return self._lock.release()

	def __enter__(self):
		self._lock.__enter__()
		self._locked = True
		return self._value

	def __exit__(self, *args, **kwargs):
		if self._locked:
			self._locked = False
			return self._lock.__exit__(*args, **kwargs)