import argparse
import configparser
import datetime
import re
import subprocess
import sys
import traceback
import zlib
from typing import AnyStr, List, Optional, Tuple, Union

from lib.pathlibex import Path


class common():
	@staticmethod
	def tdToAssTime(d: datetime.timedelta) -> str:
		seconds = d.total_seconds()
		hours = seconds // 3600
		minutes = (seconds % 3600) // 60
		seconds = seconds % 60
		return "%01d:%02d:%02d.%02d" % (hours, minutes, int(seconds), round((seconds % 1) * 100))

	@staticmethod
	def crc32f(p: Path):
		prev = 0
		for eachLine in p.open("rb"):
			prev = zlib.crc32(eachLine, prev)
		return "%08X" % (prev & 0xFFFFFFFF)

	@staticmethod
	def strip_crc(stri):
		outp = re.sub(r'(_\[[A-z0-9]{8}\])', '', stri).strip()
		outp = re.sub(r'(\[[A-z0-9]{8}\])', '', outp).strip()
		return outp

	@staticmethod
	def tdToMkvTime(d: datetime.timedelta) -> str:
		seconds = d.total_seconds()
		hours = seconds // 3600
		minutes = (seconds % 3600) // 60
		seconds = seconds % 60
		return "%02d:%02d:%02d.%09d" % (hours, minutes, int(seconds), round(seconds % 1 * 1000000000))

	@staticmethod
	def parseAssTime(s: str) -> datetime.timedelta:
		sp = s.split(".")
		if len(sp) != 2:
			print("Malformed ass time: " + s)
			exit(1)
		s = sp[0] + "." + sp[1][0:4]
		t = datetime.datetime.strptime(s, "%H:%M:%S.%f")
		return datetime.timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)

	@staticmethod
	def cmdStr(lst):
		return subprocess.list2cmdline(lst)

	@staticmethod
	def folderArgument(v) -> Path:
		p = Path(v)
		if p.exists():
			return p
		else:
			raise argparse.ArgumentTypeError('Folder %s does not exist' % (v))

	@staticmethod
	def run_process(cmd: Union[AnyStr, List], silent=False) -> str:
		p = None
		try:
			p = subprocess.Popen(cmd, shell=False, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			# p = subprocess.Popen(cmd, shell=False, bufsize=0, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
		except Exception as e:
			print(e)
			traceback.print_exc()
			print(cmd)
			exit(1)
		buffer = b""
		for line in p.stdout:
			if not silent:
				sys.stdout.write(line.decode("utf-8"))
				sys.stdout.flush()
			buffer += line

		p.wait()

		if p.returncode != 0 and p.returncode != None:
			print(F"Process exited unnormally [{p.returncode}]:")
			print("-----------")
			traceback.print_exc()
			print("-----------")
			print(subprocess.list2cmdline(cmd))
			print("-----------")
			print(buffer.decode("utf-8"))
			print("-----------")
			traceback.print_stack()
			exit(1)

		return buffer.decode("utf-8")
