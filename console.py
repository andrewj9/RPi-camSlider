from time import sleep
from UI import Interface


#Select pin numbers
up = 8
down = 7
enterButt = 25
goButt = 23
buttLED = 24
fan = 5
camFocus = 15
camTrigger = 18
#Translation Stepper Enable Pins
pinENa = 0
pinENb = 1
#Rotation Stepper Enable Pins
rPinENa = 2
rPinENb = 3
#Translational Motor Settings
pinA1 = 12
pinA2 = 16
pinB1 = 20
pinB2 = 21
stepsPerUnit = 1
xMin = 0
xMax = 11000
xButt = 10
#Rotational Motor Settings
rPinA1 = 6
rPinA2 = 13
rPinB1 = 19
rPinB2 = 26
stepsPerDeg = 1
rMin = 0
rMax = 1600
rButt = 9
#Start User Interface
interface = Interface()
interface.setTransMotor(pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, xButt, stepsPerUnit)
interface.setTransLimits(xMin, xMax)
interface.setRotMotor(rPinA1, rPinA2, rPinB1, rPinB2, rPinENa, rPinENb, rButt, stepsPerDeg)
interface.setRotLimits(rMin, rMax)
interface.populate()
interface.setControls(enterButt, goButt, buttLED, up, down)
interface.setFan(fan)
interface.setCamTrigger(camFocus, camTrigger)
interface.loadDATA()
interface.homeMotors()
interface.update()

loop = True
try:
	while loop:
		print('')
		print('=========================')
		print(interface.currentMenu.toString()[0])
		try:
			s2 = interface.currentMenu.toString()[1]
			s1 = 'Current Value: '
			print(s1 + s2)
		except:
			pass
		print('=========================')
		for n in range(interface.currentMenu.getItems().__len__()):	
			if interface.currentMenu.getItems()[n] != None:
				try:
					str1 = str(n)
					str2 = ' - '
					str3 = interface.currentMenu.getItems()[n].toString()[0]
					str4 = interface.currentMenu.getItems()[n].toString()[1]
					prop = ' - Value: '
					line = str1 + str2 + str3 + prop + str4
					print(line)
				except:
					str1 = str(n)
					str2 = ' - '
					str3 = interface.currentMenu.getItems()[n].toString()[0]
					line = str1 + str2 + str3
					print(line)
		print('')
		print('set <value>, go, or exit')
		print('')
		words = input('Enter Selection: ')
		try:
			ui = words.split(' ')

			if ui[0] == "go":
				interface.goSTART(0)
			elif ui[0] == "exit":
				loop = False
				break
			elif ui[0] == "set":
				if ui[1] == "end":
					interface.currentMenu.setVal(int(interface.currentMenu.getLimits()[1]))
					try:
						interface.currentMenu.isRecent(True)
					except:
						pass
					interface.calculate()
					interface.saveDATA()
					interface.refresh()

				elif ui[1] == "home":
					interface.currentMenu.setVal(int(interface.currentMenu.getLimits()[0]))
					try:
						interface.currentMenu.isRecent(True)
					except:
						pass
					interface.calculate()
					interface.saveDATA()
					interface.refresh()

				elif ui[1] == "middle":
					interface.currentMenu.setVal(int(interface.currentMenu.getLimits()[1]/2))
					try:
						interface.currentMenu.isRecent(True)
					except:
						pass
					interface.calculate()
					interface.saveDATA()
					interface.refresh()	
					
				try:
					interface.currentMenu.setVal(int(ui[1]))
					try:
						interface.currentMenu.isRecent(True)
					except:
						pass
					interface.calculate()
					interface.saveDATA()
					interface.refresh()
				except:
					print('Invalid Syntax')

			else:
				try:
					interface.selector = int(ui[0])
					interface.selectButt(1)
				except:
					pass
		except:
			pass
		interface.saveDATA()

	interface.off()
	print(' --> Exit Program')
	print('MotionPi: Goodbye')
except KeyboardInterrupt:
	pass
#end of file
