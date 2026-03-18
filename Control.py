#!/APSshare/anaconda3/x86_64/bin/python3

import json
import requests
import argparse

from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run

class ControlIOC(PVGroup):
	async def start_stop(self, instance, value):
		if value < 0 or value > 1:
			return instance.value

		if value == 0 and instance.value == 1:
			# Do Stop
			response = requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "stop"}), timeout=5)
			if response.status_code != 200:
				print(response.status_code)
				return instance.value

		elif value == 1 and instance.value == 0:
			# Do Start
			response = requests.put(self.url + "/filewriter/config/mode", json.dumps({"value" : "start"}), timeout=5)
			
			if response.status_code != 200:
				print(response.status_code)
				return instance.value
		else:
			return instance.value

		return value


	Acquire = pvproperty(value=0, put=start_stop)



if __name__ == '__main__':
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

	ioc_options, run_options = ioc_arg_parser(
		default_prefix=args.prefix + 'cam1:',
		desc='IOC')
	citius_control = ControlIOC(**ioc_options)
	citius_control.url = 'http://%s:%d' % (args.ip, args.port)

	run(citius_control.pvdb, **run_options)
