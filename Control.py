#!/APSshare/anaconda3/x86_64/bin/python3

import json
import requests
import argparse

from caproto import ChannelType, SkipWrite
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run, scan_wrapper, get_pv_pair_wrapper

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
			raise SkipWrite
			
		if value == 0 and instance.value == 1:
			pass
			
		elif value == 1 and instance.value == 0:
			# Do Start
			try:
				response = await requests.put(self.url + "/filewriter/config/ntrains", json.dumps({"value" : self.numimages.readback.value}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
			
				response = await requests.put(self.url + "/filewriter/config/output_dir", json.dumps({"value" : self.OutputDir.value}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
				
				response = await requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "start"}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
				
				await self.AcquireBusy.write("Acquiring")
				await self.DetectorState_RBV.write("Acquire")
					
			except Exception as e:
				await self.DetectorState_RBV.write("Error")
				await self.StatusMessage_RBV.write(str(e)[0:255])
				raise SkipWrite
				
		else:
			raise SkipWrite

		await self.StatusMessage_RBV.write("")
		return value


	# PV's
	Acquire = pvproperty(value=0, put=start_stop)
	AcquireBusy = pvproperty(dtype=ChannelType.ENUM, enum_strings=("Done", "Acquiring"))
	DetectorState_RBV = pvproperty(dtype=ChannelType.ENUM, enum_strings=("Idle", "Acquire", "Readout", "Correct", "Saving", "Aborting", "Error"))
	StatusMessage_RBV = pvproperty(value="", dtype=ChannelType.STRING, max_length=255)
	status_check = pvproperty(value="")
	OutputDir = pvproperty(value="", dtype=ChannelType.STRING, max_length=255)
	
	pair_pvs = get_pv_pair_wrapper(setpoint_suffix='',
						           readback_suffix='_RBV')
						
	numimages = pair_pvs(name="NumImages", value=0)
	
	@numimages.setpoint.putter
	async def numimages(obj, instance, value):
		await obj.readback.write(value)
						
			
	@status_check.scan(period=1.0)
	async def status_check(self, instance, async_io):
		if self.DetectorState_RBV.value != 1:
			return
		
		try:
			response = await requests.get(self.url + "/filewriter/config/mode", timeout=1)
			
			if response.json()["value"] == "start":
				return
				
			response = await requests.get(self.url + "/filewriter/status/waiting_ntrains", timeout=1)
			
			if response.json()["value"] == 0:
				await self.Acquire.write(0)
				await self.AcquireBusy.write("Done")
				await self.DetectorState_RBV.write("Idle")
				await self.StatusMessage_RBV.write("")
		except:
			pass

			
			
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
	
	
	
