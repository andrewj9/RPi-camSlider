import threading
import RPi.GPIO as GPIO
import time
from time import sleep

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

class fanThread(threading.Thread):
	def __init__(self, pin, threadID, name, period, dutyCycle, event):
		threading.Thread.__init__(self)
		self.pin = pin
		self.initPin()
		self.threadID = threadID
		self.name = name
		self.period = period
		self.dutyCycle = dutyCycle
		self.event = event
		return

	def on(self):
		GPIO.output(self.pin, False)
		return

	def off(self):
		GPIO.output(self.pin, True)
		return        

	def initPin(self):
		GPIO.setup(self.pin, GPIO.OUT)
		GPIO.output(self.pin, True)
		return

	def run(self):
		while True:
			while self.event.isSet():
				ti = time.monotonic()
				self.on()
				while (time.monotonic() - ti) < (self.dutyCycle*self.period) and self.event.isSet():
					sleep(0.5)
				self.off()
				while (time.monotonic() - ti) < (1 - self.dutyCycle)*self.period and self.event.isSet():
					sleep(0.5)
			self.off()
			sleep(0.5)
		return

class Fan(object):
	def __init__(self, pin, speed, dutyCycle, period):
		self.pin = pin
		self.speed = speed  # (Not Implemented)
		self.dutyCycle = dutyCycle
		self.period = period
		self.stopEvent = threading.Event()
		self.stopEvent.set()
		self.cycle = fanThread(self.pin, 8, "Cooler", self.period, self.dutyCycle, self.stopEvent)
		self.cycle.start()
		return
		
	def on(self):
		self.stopEvent.set()
		return

	def off(self):
		self.stopEvent.clear()
		return