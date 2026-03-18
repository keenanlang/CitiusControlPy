#!/APSshare/anaconda3/x86_64/bin/python3

import json
import requests
import argparse

from caproto import ChannelType
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run, scan_wrapper

#########################
#   IOC Implementation  #
#########################

class ControlIOC(PVGroup):
	def initialize(self):
		#Attempt to initialize API
		try:
			response = requests.put(self.url + "/detector/command/initialize", json.dumps({"nprbs" : 1}), timeout=5)

			if response.status_code != 200:
				raise Exception("failed to initialize detector")
				
		except:
			raise Exception("timeout connecting to detector")
			
			
	async def start_stop(self, instance, value):
		if value < 0 or value > 1:
			return instance.value

		if value == 0 and instance.value == 1:
			pass
			
			# # Do Stop
			# try:
				# response = requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "stop"}), timeout=5)
				
				# if response.status_code != 200:
					# await self.DetectorState_RBV.write("Error")
					# await self.StatusMessage_RBV.write("Non-success response from API: %s" % response.status_code)
					# return instance.value
				
			# except:
				# await self.DetectorState_RBV.write("Error")
				# await self.StatusMessage_RBV.write("Timeout error")
				# return instance.value
			
		elif value == 1 and instance.value == 0:
			# Do Start
			try:
				response = requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "start"}), timeout=5)
				
				if response.status_code != 200:
					await self.DetectorState_RBV.write("Error")
					await self.StatusMessage_RBV.write("Non-success response from API: %s" % response.status_code)
					return instance.value
				
				await self.AcquireBusy.write("Acquiring")
				await self.DetectorState_RBV.write("Acquire")
					
			except:
				await self.DetectorState_RBV.write("Error")
				await self.StatusMessage_RBV.write("Timeout error")
				return instance.value
				
		else:
			return instance.value

		await self.StatusMessage_RBV.write("")
		return value


	# Start/Stop
	Acquire = pvproperty(value=0, put=start_stop)
	AcquireBusy = pvproperty(dtype=ChannelType.ENUM, enum_strings=("Done", "Acquiring"))
	DetectorState_RBV = pvproperty(dtype=ChannelType.ENUM, enum_strings=("Idle", "Acquire", "Readout", "Correct", "Saving", "Aborting", "Error"))
	StatusMessage_RBV = pvproperty(value="")
	status_check = pvproperty(value="")
	
	@status_check.scan(period=1.0)
	async def status_check(self, instance, async_io):
		if self.DetectorState_RBV.value == 0:
			return
		
		response = requests.get(self.url + "/filewriter/config/mode", timeout=1)
		
		if response.json()["value"] == "start":
			return
			
		response = requests.get(self.url + "/filewriter/status/waiting_ntrains", timeout=1)
		
		if response.json()["value"] == 0:
			await self.Acquire.write(0)
			await self.AcquireBusy.write("Done")
			await self.DetectorState_RBV.write("Idle")
			await self.StatusMessage_RBV.write("")

			
			
####################
#  Startup Script  #
####################
			
if __name__ == '__main__':
	
	# Setup commandline args
	parser = argparse.ArgumentParser(prog='Control.py', usage='%(prog)s [OPTIONS]', formatter_class=argparse.RawTextHelpFormatter, exit_on_error=True)
	parser.add_argument("--ip", metavar="IP", dest="ip", action="store", type=str, default="192.168.1.33", help="""\
IP Address for the Citius Web API, default is 192.168.1.33
""")

	parser.add_argument("--port", metavar="PORT", dest="port", action="store", type=int, default=30303, help="""\
Network port for the Citius Web API, default is 30303
""")

	parser.add_argument("--prefix", metavar="PREFIX", dest="prefix", action="store", type=str, default="citius:", help="""\
IOC Prefix for PVs, default is "citius:". PVs will also have "cam1:" prepended.
""")

	args = parser.parse_args()
	
	# Create IOC
	ioc_options, run_options = ioc_arg_parser(
		default_prefix=args.prefix + 'cam1:',
		desc='IOC')
	
	citius_control = ControlIOC(**ioc_options)
	citius_control.url = 'http://%s:%d' % (args.ip, args.port)

	try:
		citius_control.initialize()
		run(citius_control.pvdb, **run_options)
	except Exception as e:
		print("Error starting IOC:", e)
	
	
	
