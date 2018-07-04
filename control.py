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
rMax = 1200
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

try:
	while 1:
		sleep(60)
except KeyboardInterrupt:
	interface.off()
