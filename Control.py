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
				if int(self.numimages.readback.value) <= 0:
					raise Exception("NumImages must be > 0")
					
				if int(self.numexposures.readback.value) <= 0:
					raise Exception("NumExposures must be > 0")

				metadata, values = await self.OutputDir.read(ChannelType.STRING)
				
				if len(values[0]) == 0:
					raise Exception("Must define OutputDir")
					
				response = requests.put(self.url + "/filewriter/config/ntrains", json.dumps({"value" : int(self.numimages.readback.value)}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
					
				response = requests.put(self.url + "/detector/config/sum_ntrains", json.dumps({"value" : int(self.numexposures.readback.value)}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
			
				response = requests.put(self.url + "/filewriter/config/output_dir", json.dumps({"value" : str(values[0])}), timeout=5)
				
				if response.status_code != 200:
					raise Exception("Non-success response from API: %s" % response.status_code)
				
				response = requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "start"}), timeout=5)
				
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
						
	numimages    = pair_pvs(name="NumImages", value=0)
	numexposures = pair_pvs(name="NumExposures", value=0)
	imagemode = pair_pvs(name="ImageMode", dtype=ChannelType.ENUM, enum_strings=("Uncompressed", "Zstandard", "Bitshuffle+LZ4", "LZ4"))
	
	@numimages.setpoint.putter
	async def numimages(obj, instance, value):
		await obj.readback.write(value)
		
	@numexposures.setpoint.putter
	async def numexposures(obj, instance, value):
		await obj.readback.write(value)
						
	@imagemode.setpoint.putter
	async def imagemode(obj, instance, value):				
		try:
			response = requests.put(obj.parent.url + "/filewriter/config/compression", json.dumps({"value" : str(value)}), timeout=5)
		
			if response.status_code != 200:
				raise SkipWrite("Response Code: " + str(response.status_code))
			
		except Exception as e:
			print(obj.parent.prefix, "ImageMode", e)
			raise SkipWrite 
		
		response = requests.get(obj.parent.url + "/filewriter/config/compression")
			
		await obj.readback.write(str(response.json()["value"]))
		
			
	@status_check.scan(period=1.0)
	async def status_check(self, instance, async_io):
		if str(self.DetectorState_RBV.value) != "Acquire":
			return
		
		try:
			response = requests.get(self.url + "/filewriter/config/mode", timeout=1)
			
			if str(response.json()["value"]) == "start":
				return
				
			response = requests.get(self.url + "/filewriter/status/waiting_ntrains", timeout=1)
			
			if int(response.json()["value"]) == 0:
				await self.Acquire.write(0)
				await self.AcquireBusy.write("Done")
				await self.DetectorState_RBV.write("Idle")
				await self.StatusMessage_RBV.write("")
		except Exception as e:
			print(e)
			pass

			
			
####################
#  Startup Script  #
####################
			
if __name__ == '__main__':
	
	# Setup commandline args
	myparser = argparse.ArgumentParser(prog='Control.py', usage='%(prog)s [OPTIONS]', formatter_class=argparse.RawTextHelpFormatter, exit_on_error=True)
	myparser.add_argument("--ip", metavar="IP", dest="ip", action="store", type=str, default="192.168.1.33", help="""\
IP Address for the Citius Web API, default is 192.168.1.33
""")

	myparser.add_argument("--port", metavar="PORT", dest="port", action="store", type=int, default=30303, help="""\
Network port for the Citius Web API, default is 30303
""")

	myparser.add_argument("--prefix", metavar="PREFIX", dest="prefix", action="store", type=str, default="citius:", help="""\
IOC Prefix for PVs, default is "citius:". PVs will also have "cam1:" prepended.
""")

	args = myparser.parse_args()
	
	# Create IOC	
	citius_control = ControlIOC(prefix=args.prefix+"cam1:")
	citius_control.url = 'http://%s:%d' % (args.ip, args.port)
	
	try:
		citius_control.initialize()
		print(citius_control.prefix + " Connected to Detector")
		
		run(citius_control.pvdb)
	except Exception as e:
		print("Error starting IOC:", e)
	
	
	
