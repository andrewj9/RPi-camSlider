# This class is intended to provide bipolar stepper motor control with half-stepping
# using a PCA9685 I2C LED driver as a PWM generator.  PWM signals are sent to
# Enable pins A and B on a L298N H-Bridge.
# Author: Andrew S Johnson (andrewj9@gmail.com)

from time import sleep
import math
import RPi.GPIO as GPIO
import PCA9685
import threading
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Stepper(object):
	
	def __init__(self, pinA1, pinA2, pinB1, pinB2, pinENa, pinENb, end):

		#Assign pins to stepper coils
		self.A1 = pinA1	                        # Coil A, Pin 1
		self.A2 = pinA2                     	# Coil A, Pin 2
		self.B1 = pinB1	                        # Coil B, Pin 1
		self.B2 = pinB2	                        # Coil B, Pin 2
		self.EnableA = pinENa                   # A Coil Enable Pin
		self.EnableB = pinENb                   # B Coil Enable Pin
		self.pwmFrequency = 1500                # PWM Frequency in Hertz
		self.driveDutyCycle = int(4095*0.7)     # 70% Duty Cycle
		self.lowHoldDutyCycle = int(4095*0.55)	# 55% Duty Cycle
		self.highHoldDutyCycle = int(4095*0.65)	# 65% Duty Cycle
		self.offDutyCycle = 0	                # 0% Duty Cycle
		self.holdDuty = self.lowHoldDutyCycle
		self.clearSet = True	                # Can the thread clear its own event?
		self.exitFlag = False	                # Exit Flag (Not Implemented)
		self.defaultEvent = threading.Event()	# Default event for maintenance or manual movement
		
		# GPIO Pin Setup
		GPIO.setup(self.A1, GPIO.OUT)
		GPIO.setup(self.A2, GPIO.OUT)
		GPIO.setup(self.B1, GPIO.OUT)
		GPIO.setup(self.B2, GPIO.OUT)

		#Assign pin to limit switch
		self.endSwitch = end
		GPIO.setup(self.endSwitch, GPIO.IN, pull_up_down = GPIO.PUD_UP)

		#Set up PWM Output
		self.pi = PCA9685.PCA9685()
		self.pi.set_pwm_freq(self.pwmFrequency)
		self.pi.set_pwm(self.EnableA, 0, self.lowHoldDutyCycle)
		self.pi.set_pwm(self.EnableB, 0, self.lowHoldDutyCycle)

		#Call initial position zero
		self.position = 0

		#Set initial Limits
		self.Limits = [0,1]

		#Define half-steps
		self.step1 = [1,0,0,0]
		self.step2 = [1,0,1,0]
		self.step3 = [0,0,1,0]
		self.step4 = [0,1,1,0]
		self.step5 = [0,1,0,0]
		self.step6 = [0,1,0,1]
		self.step7 = [0,0,0,1]
		self.step8 = [1,0,0,1]

		#Define step sequence
		self.steps = [self.step1, self.step2, self.step3, self.step4, self.step5, self.step6, self.step7, self.step8]

		#Set current step to zero
		self.currentStep = 0
		self.reverse = False
		return

	#Invert the motor step sequence
	def invert(self):
		self.steps = [self.step8, self.step7, self.step6, self.step5, self.step4, self.step3, self.step2, self.step1]
		return

	#Assign limits to movement
	def setLimits(self, l1, l2):
		self.Limits = [l1, l2]
		return
			
	#Set output values to GPIO
	def setStep(self, val):
		GPIO.output(self.A1, val[0])
		GPIO.output(self.A2, val[1])
		GPIO.output(self.B1, val[2])
		GPIO.output(self.B2, val[3])
		return

	#Turn off PWM output
	def OFF(self):
		self.pi.set_pwm(self.EnableA, 0, self.offDutyCycle)
		self.pi.set_pwm(self.EnableB, 0, self.offDutyCycle)
		return

	#Set PWM duty cycle to hold
	def pwmHold(self):
		self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
		self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		return

	#Set PWM duty cycle to drive
	def pwmDrive(self):
		self.pi.set_pwm(self.EnableA, 0, self.driveDutyCycle)
		self.pi.set_pwm(self.EnableB, 0, self.driveDutyCycle)
		return

	#Set pwm hold duty cycle to specified level
	def pwmHoldSet(self, level):
		if level == 0:
			self.holdDuty = self.offDutyCycle
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		elif level == 1:
			self.holdDuty = self.lowHoldDutyCycle
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		elif level == 2:
			self.holdDuty = self.highHoldDutyCycle
			self.pi.set_pwm(self.EnableA, 0, self.holdDuty)
			self.pi.set_pwm(self.EnableB, 0, self.holdDuty)
		return

	#Drive the motor a defined number of steps and increment
	def drive(self, threadname, event, steps, increment, delay):
		if ~self.reverse:	# Check inverter value to determine direction of travel
			if steps > 0:
				self.forward(threadname, event, steps, increment, delay)
			elif steps < 0:
				self.backward(threadname, event, -steps, increment, delay)
		else:
			if steps > 0:
				self.backward(threadname, event, steps, increment, delay)
			elif steps < 0:
				self.forward(threadname, event, -steps, increment, delay)
		return

	#Drive to a specified position between physical limits, determine inter-step delay based on total distance
	def goTo(self, val):
		if math.fabs(val - self.getPosition()) < 100:
			delay = 0.01
		elif math.fabs(val - self.getPosition()) < 1000 or self.holdDuty == self.highHoldDutyCycle:
			delay = 0.005
		else:
			delay = 0.001
		self.clearSet = False	# Disable self-clearing of event (Go the whole distance without stopping incrementally)
		self.defaultEvent.set()	# Set the wait event (Don't stop for nobody)
		self.drive("GoTo", self.defaultEvent, val - self.getPosition(), val - self.getPosition(), delay)
		return

	#Drive motor in the primary direction a specified number of steps using the specified increment
	def forward(self, threadName, event, steps, increment, delay):
		currentStep = 0
		step = []
		for i in range(0, steps):
			if self.currentStep < self.steps.__len__()-1:	# Check to see where we are in the step table
				self.currentStep += 1	                    # If we're not yet at the end of the step table, make the next step the current step
			else:
				self.currentStep = 0
			step.append(self.steps[self.currentStep])
		self.pwmDrive()
		i = 1                                                   # Init Counter
		while steps:	                                        # Stay in the race until the finish line is crossed
			if self.position < self.Limits[1]:	                # If we are within the physical limits, you may proceed
				if self.clearSet and i >= increment:	            # Are we self-clearing the event for incremental operation?
					event.clear()	                            # Clear it
					i = 0	                                    # Reset the step counter
				i += 1	                                        # Increment the step counter
				if self.exitFlag:	                            # Check for exit flag (Not Implemented)
					threadName.exit()	                        # Exit this crazy thread
				self.setStep(step[currentStep])	    # Update the GPIO output to represent the current step
				self.position += 1	                            # Increment the position tracker
				steps -= 1	                                    # Remove one step from the step counter
				currentStep += 1
				sleep(delay)	                                # Take a breath and wait for the motor rotor to get settled in
				event.wait()	                                # Wait here until the boss says it's okay to move again (Only if the event has been cleared)
			else:
				self.backward(threadName, event, steps, increment, delay)	# If we're at the end of our physical limits, turn around and go back
		self.pwmHold()                                          # Relax the duty cycle and reduce the current flowing through the coils
		event.clear()	                                        # Clean up before leaving
		return

	#Drive motor in the secondary direction a specified number of steps using the specified increment
	def backward(self, threadName, event, steps, increment, delay):
		currentStep = steps - 1
		step = []
		for i in range(0, steps):
			if self.currentStep < self.steps.__len__()-1:	# Check to see where we are in the step table
				self.currentStep += 1	                    # If we're not yet at the end of the step table, make the next step the current step
			else:
				self.currentStep = 0
			step.append(self.steps[self.currentStep])
		self.pwmDrive()                                         # Set PWM duty cycle to drive setting
		i = 1                                                   # Init Counter
		while steps:                                            # Stay in the race until the finish line is crossed
			if self.position > self.Limits[0]:                  # If we are within the physical limits, you may proceed
				if self.clearSet and i >= increment:             # Are we self-clearing the event for incremental operation?
					event.clear()                               # Clear it
					i = 0                                       # Reset the step counter
				i += 1                                          # Increment the step counter
				if self.exitFlag:                               # Check for exit flag (Not Implemented)
					threadName.exit()                           # Exit this crazy thread
				self.setStep(step[currentStep])      # Update the GPIO output to represent the current step
				self.position -= 1                              # Decrement the position tracker
				steps -= 1                                      # Remove one step from the step counter
				currentStep -= 1                                # If we're not yet at the beginning of the step table, make the previous step the current step
				sleep(delay)                                    # Take a breath and wait for the motor rotor to get settled in
				event.wait()                                    # Wait here until the boss says it's okay to move again (Only if the event has been cleared)
			else:
				self.forward(threadName, event, steps, increment, delay)    # If we're at the end of our physical limits, turn around and go back
		event.clear()                                           # Clean up before leaving
		self.pwmHold()                                          # Relax the duty cycle and reduce the current flowing through the coils
		return

	#Return current position of motor
	def getPosition(self):
		return self.position

	#Set current position of motor
	def setPosition(self, val):
		self.position = int(val)
		return

	#Drive motor in the secondary direction until limit switch is triggered, then move away from the switch for 100 steps and set position to zero
	def calibrate(self):
		self.pwmDrive()                                         # Set PWM duty cycle to drive setting
		self.reverse = False                                    # Make sure we're going the right direction
		while GPIO.input(self.endSwitch) == False:              # Keep going until we bump into something
			self.setStep(self.steps[self.currentStep])          # Update the GPIO output to represent the current step
			self.position -= 1                                  # Decrement the position tracker (Probably unnecessary for this procedure)
			sleep(0.002)                                        # Take a breath and wait for the motor rotor to get settled in
			if self.currentStep > 0:                            # Check to see where we are in the step table
				self.currentStep -= 1                           # If we're not yet at the beginning of the step table, make the previous step the current step
			else:
				self.currentStep = 7                            # If we are at the beginning of the step table, make the last step the current step
		self.defaultEvent.set()                                 # Set the event so we can blow right through the cycle
		self.clearSet = False                                   # Don't automatically clear the event
		self.forward("Jerry", self.defaultEvent, 100, 100, 0.002)   # Drive us forward 100 steps, Jerry!
		self.pwmHold()                                          # Relax the duty cycle and reduce the current flowing through the coils
		self.zeroPosition()                                     # Set the position tracker to zero
		self.clearSet = True                                    # Restore event self-clearing for incremental operation
		return

	#Set current position to zero
	def zeroPosition(self):
		self.position = 0
		return
