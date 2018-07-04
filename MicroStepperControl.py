from time import sleep
import math
import numpy
import RPi.GPIO as GPIO
import PCA9685

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Stepper(object):
	
	def __init__(self, pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, end):

		#Assign pins to stepper coils
		self.A1 = pinA1
		self.A2 = pinA2
		self.B1 = pinB1
		self.B2 = pinB2
		self.EnableA = pinENa
		self.EnableB = pinENb
		self.pwmA = 0
		self.pwmB = 0
		self.delay = [0, 0.00002, 0.0002, 0.001]
		self.dt = 3
		self.MicroStep = int(MicroStep)
		self.pwmFrequency = 1526
		self.dutyRange = [0,4095] 
		self.driveDutyCycle = int(self.dutyRange[1]*0.7)
		self.lowHoldDutyCycle = int(self.dutyRange[1]*0.5)
		self.highHoldDutyCycle = int(self.dutyRange[1]*0.6)
		self.offDutyCycle = int(self.dutyRange[0])
		self.holdDuty = int(self.lowHoldDutyCycle)
		self.Flag = False
		self.gpioMask = 1<<self.A1 | 1<<self.B1 | 1<<self.A2 | 1<<self.B2
		GPIO.setup(self.A1, GPIO.OUT)
		GPIO.setup(self.A2, GPIO.OUT)
		GPIO.setup(self.B1, GPIO.OUT)
		GPIO.setup(self.B2, GPIO.OUT)

		#Assign pins to limit switches
		self.endSwitch = end
		GPIO.setup(self.endSwitch, GPIO.IN, pull_up_down = GPIO.PUD_UP)

		#Set up PWM
		self.pi = PCA9685.PCA9685()
		self.pi.set_pwm_freq(self.pwmFrequency)

		#Call initial position zero
		self.position = 0

		#Set initial Limits
		self.Limits = [0,1]

		#Define step sequence
		self.stepTable = [self.step0, self.step1, self.step2, self.step3, self.step4, self.step5, self.step6, self.step7, self.step8, self.step9, self.step10, self.step11, self.step12, self.step13, self.step14, self.step15]

		#Set current step to zero
		self.currentStep = 0
		self.reverse = False
		self.BuildMicroStepTable()
		return

	def BuildMicroStepTable(self):
		self.TableSize = int(self.MicroStep * 4)
		self.coilTable = numpy.zeros(self.TableSize, dtype = numpy.uint32)
    	self.pwmATable = numpy.zeros(self.TableSize, dtype = numpy.int16)
    	self.pwmBTable = numpy.zeros(self.TableSize, dtype = numpy.int16)
    	#calculate CoilTable for gpio
    	HalfSize = int(self.TableSize/2)
    	for i in range(HalfSize):
      		self.coilTable[i] = 1 << self.A1
    	for i in range(HalfSize,self.TableSize):
      		self.coilTable[i] = 1 << self.A2
    	for i in range(HalfSize):
      		self.coilTable[i+self.MicroStep]= self.coilTable[i+self.MicroStep] | (1 << self.B1)
    	for i in range(HalfSize, self.TableSize):
      		self.coilTable[(i+self.MicroStep) % self.TableSize]= self.coilTable[(i+self.MicroStep) % self.TableSize] | (1 << self.B2)
    	# calculate PWM
   		for i in range(self.TableSize):
      		PValue =  math.sqrt(math.fabs(math.sin(math.pi * i / (self.TableSize / 2.0))))
      		self.pwmATable[i]= math.floor(self.PwmRange * PValue)
      		self.pwmBTable[(i + self.MicroStep) % self.TableSize]= self.pwmATable[i]

	#Invert the motor steps
	def invert(self):
		self.steps = [self.step15, self.step14, self.step13, self.step12, self.step11, self.step10, self.step9, self.step8, self.step7, self.step6, self.step5, self.step4, self.step3, self.step2, self.step1, self.step0]
		return

	#Assign limits to movement
	def setLimits(self, l1, l2):
		self.Limits = [l1, l2]
		return
			
	#Set output values
	def setStep(self, step):
		GPIO.output(self.A1, step[0])
		GPIO.output(self.A2, step[1])
		GPIO.output(self.B1, step[2])
		GPIO.output(self.B2, step[3])
		self.pi.set_pwm(self.EnableA, 0, step[4] + 1000)
		self.pi.set_pwm(self.EnableB, 0, step[5] + 1000)
		return

	def setStepper(self,position):
        if(self.Flag):
       	    #set gpio
       		index = position % self.TableSize
       		setmask = self.coilTable[index]
       		#set PWM
       		self.pi.set_PWM_dutycycle(self.EnableA, 0, self.pwmATable[index]*0.8)
       		self.pi.set_PWM_dutycycle(self.EnableB, 0, self.pwmBTable[index]*0.8)
       		self.Position= position

	#Turn off current to motor
	def OFF(self):
		self.pi.set_pwm(self.EnableA, 0, self.offDutyCycle)
		self.pi.set_pwm(self.EnableB, 0, self.offDutyCycle)
		return

	#Turn off PWM
	def pwmHold(self):
		self.pi.set_pwm(self.EnableA, 0, self.pwmA)
		self.pi.set_pwm(self.EnableB, 0, self.pwmB)
		return

	#Set PWM output to Drive Duty Cycle
	def pwmDrive(self):
		self.pi.set_pwm(self.EnableA, 0, self.driveDutyCycle)
		self.pi.set_pwm(self.EnableB, 0, self.driveDutyCycle)
		return

	#Set PWM output to specified holding Duty Cycle
	def pwmHoldSet(self, level):
		if level == 0:
			self.holdDuty = int(self.offDutyCycle)
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		elif level == 1:
			self.holdDuty = int(self.lowHoldDutyCycle)
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		elif level == 2:
			self.holdDuty = int(self.highHoldDutyCycle)
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		return

	#Drive the motor a defined number of steps
	def drive(self, steps):
		if ~self.reverse:
			if steps > 0:
				self.forward(steps)
			elif steps < 0:
				self.backward(-steps)
		else:
			if steps > 0:
				self.backward(steps)
			elif steps < 0:
				self.forward(-steps)
		return

	#Drive to a specified position
	def goTo(self, val):
		self.drive(val - self.getPosition())
		return

	#Drive motor forward a defined number of steps, then turn off
	def forward(self, steps):
		for step in range(0, steps):
			if self.position < self.Limits[1]:
				self.setStep(self.stepTable[self.currentStep])
				self.position += 1
				if self.currentStep < self.stepTable.__len__()-1:
					self.currentStep +=1
				else:
					self.currentStep = 0
					sleep(self.delay[self.dt])
			else:
				self.reverse = ~self.reverse
				break
		self.pwmHold()
		return

	#Drive motor backward a defined number of steps, then turn off
	def backward(self, steps):
		for step in range(0, steps):
			if self.position > self.Limits[0]:
				self.setStep(self.stepTable[self.currentStep])
				self.position -= 1
				if self.currentStep > 0:
					self.currentStep -=1
				else:
					self.currentStep = self.stepTable.__len__()-1
					sleep(self.delay[self.dt])
			else:
				self.reverse = ~self.reverse
				break
		self.pwmHold()
		return

	#Return current position of motor
	def getPosition(self):
		return int(self.position)

	#Set current position of motor
	def setPosition(self, val):
		self.position = int(val)
		return

	#Drive motor in reverse until end switch is triggered, then set position to zero
	def calibrate(self):
		self.reverse = False
		while GPIO.input(self.endSwitch) == False:
			self.setStep(self.steps[self.currentStep])
			self.position -= 1
			sleep(0.002)
			if self.currentStep > 0:
				self.currentStep -= 1
			else:
				self.currentStep = self.stepTable.__len__()-1
		self.OFF()
		self.forward(400)
		self.zeroPosition()
		return

	#Set current position to zero
	def zeroPosition(self):
		self.position = 0
		return
