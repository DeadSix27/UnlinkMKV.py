from __future__ import annotations

import datetime
import json
import os
import random
import re
from typing import AnyStr, Dict, List, Optional, Tuple, Union

from lxml import objectify

from lib.common import common
from lib.pathlibex import Path

ASS_STYLE_RE: re() = re.compile(r'Style: (?P<name>[^,]+),(?P<font_family>[^,]+),(?P<font_size>[^,]+),(?P<color_primary>[^,]+),(?P<color_secondary>[^,]+),(?P<color_outline>[^,]+),(?P<color_back>[^,]+),(?P<is_bold>[^,]+),(?P<is_italic>[^,]+),(?P<is_underline>[^,]+),(?P<is_strikeout>[^,]+),(?P<scale_x>[^,]+),(?P<scale_y>[^,]+),(?P<spacing>[^,]+),(?P<angle>[^,]+),(?P<border_style>[^,]+),(?P<outline>[^,]+),(?P<shadow>[^,]+),(?P<alignment>[^,]+),(?P<margin_l>[^,]+),(?P<margin_r>[^,]+),(?P<margin_v>[^,]+),(?P<encoding>[^,]+)')
DIALOGUE_RE: re() = re.compile(r'^(?P<part1>(?:(Comment|Dialogue): )(?:[-+?0-9\.]+),(?P<start>[-+?0-9\.\:]+),(?P<end>[-+?0-9\.\:]+),)(?P<style_name>[^,]*)(?P<part2>,(?:[^,]+)?,(?:[^,]+)?,(?:[^,]+)?,(?:[^,]+)?,(?:[^,]+)?,(?P<subtext>.+)?)$')


class mkvstuff:

	@staticmethod
	def style_to_dict(dl):
		dl = dl.strip()
		m = ASS_STYLE_RE.match(dl)
		if m:
			return m.groupdict()
		else:
			return None
	#:
	@staticmethod
	def dict_to_style(style_dict):
		style_format_str = 'Style: {name},{font_family},{font_size},{color_primary},{color_secondary},{color_outline},{color_back},{is_bold},{is_italic},{is_underline},{is_strikeout},{scale_x},{scale_y},{spacing},{angle},{border_style},{outline},{shadow},{alignment},{margin_l},{margin_r},{margin_v},{encoding}'
		return style_format_str.format(**style_dict)
	#:

	@staticmethod
	def getChapterDict(file_path: Path) -> Union[List[Dict], None]:
		output = None
		if mkvstuff.has_chapters(file_path):
			chapter_file: Path = mkvstuff.extract_chapter(file_path)
			xml = None
			with open(chapter_file, "r", encoding="utf-8") as f:
				xml = f.read()
			root = objectify.fromstring(xml)
			previous_end = "00:00:00.000000000"
			i = 0
			for x in root.EditionEntry.getchildren():
				if x.tag == "ChapterAtom":
					i += 1
					if not output:
						output = {}
					name = "?"
					segment = None
					endtime = None
					if hasattr(x, 'ChapterDisplay') and hasattr(x.ChapterDisplay, "ChapterString"):
						name = x.ChapterDisplay.ChapterString.text
					if hasattr(x, 'ChapterSegmentUID'):
						segment = x.ChapterSegmentUID.text
					if hasattr(x, 'ChapterTimeEnd'):
						endtime = x.ChapterTimeEnd.text
					output[i] = (
						{
							"name": name,
							"segment_uid": segment,
							"time_start": x.ChapterTimeStart.text,
						}
					)
					if endtime:
						output[i]["time_end"] = endtime
					output[i]["previous_end"] = str(previous_end)
					if hasattr(x, 'ChapterTimeEnd'):
						previous_end = x.ChapterTimeEnd.text
					else:
						previous_end = None
			chapter_file.unlink()
		return output

	@staticmethod
	def replaceSubFileWith(input_file: Path, sub_file: Path, output_folder: Path):
		output_tmp1 = output_folder.joinpath(input_file.append_stem('_fxd_sub_tmp1').name)
		cmd = [
			'ffmpeg',
			'-y',
			'-i',
			F'{input_file}',
			'-map_metadata',
			'0',
			'-sn',
			'-c',
			'copy',
			F'{output_tmp1}'
		]
		common.run_process(cmd, silent=True)
		
		output_tmp = output_folder.joinpath(input_file.append_stem('_fxd_sub').name)
		cmd = [
			'ffmpeg',
			'-y',
			'-i',
			F'{output_tmp1}',
			'-i',
			F'{sub_file}',
			'-map_metadata',
			'0',
			'-c',
			'copy',
			F'{output_tmp}'
		]
		common.run_process(cmd, silent=True)
		output_tmp1.unlink()
		return output_tmp

	@staticmethod
	def getStylesFromAssFile(input_file: Path):
		styles = []
		with input_file.open("r", encoding="utf-8-sig") as f:
			for line in f:
				if ASS_STYLE_RE.match(line):
					styles.append(line.strip())
		return styles

	@staticmethod
	def suffixStyleNaming(input_file: Path, style_suffix: str):
		print(F"adding suffix '{style_suffix}' to styles in: {input_file.name}")
		output_tmp = input_file.append_stem("_tmp")
		new_file = []

		with input_file.open('r', encoding='utf-8-sig') as f:
			for line in f:
				line = line.strip()
				m = DIALOGUE_RE.search(line)
				if ASS_STYLE_RE.match(line):
					styleDict = mkvstuff.style_to_dict(line)
					styleDict["name"] = styleDict["name"] + "_" + style_suffix
					new_file.append(mkvstuff.dict_to_style(styleDict))
				elif m:
					gd = m.groupdict()
					newLine = gd["part1"] + gd["style_name"] + "_" + style_suffix + gd["part2"]
					new_file.append(newLine)
				elif "Dialogue:" in line or "Comment:" in line:
					print("Failed to rx parse: \n " + line)
					print("The subfile is probably fucked, lack of proper QA in fansubs..")
					exit(1)
				else:
					new_file.append(line)

		with output_tmp.open('w', encoding='utf-8-sig') as nf:
			nf.write("\n".join(new_file))
		input_file.unlink()
		output_tmp.move(input_file)
		return input_file

	@staticmethod
	def replaceAssStylesWithList(input_file: Path, style_list: dict):
		print(F"replacing styles in: {input_file.name}")
		output_tmp = input_file.append_stem("_tmp")
		new_file = []
		with input_file.open('r', encoding='utf-8-sig') as f:
			for line in f:
				line = line.strip()
				if re.match(r'^Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding$', line):
					new_file.append(line)
					for styleName, styleDict in style_list.items():
						new_file.append(mkvstuff.dict_to_style(styleDict))
				elif not ASS_STYLE_RE.match(line):
					new_file.append(line)

		with output_tmp.open('w', encoding='utf-8-sig') as nf:
			nf.write("\n".join(new_file))
		input_file.unlink()
		output_tmp.move(input_file)
		return input_file

	@staticmethod
	def get_attachment_list(p):
		dat = mkvstuff.mkvJson(p)
		flist = []
		if 'attachments' not in dat:
			return flist
		for a in dat['attachments']:
			p = Path(a['file_name'])
			flist.append({'id': a['id'], "type": "attachments", "ext": p.suffix, 'delay': 0, 'lang': 'eng', 'codec': a['content_type'], 'name': a['file_name']})
		return flist

	@staticmethod
	def extract_first_subtitle(input_file: Path, output_folder: Path = None):
		output = input_file.change_suffix(".ass")
		if output_folder:
			output = output_folder.joinpath(input_file.change_suffix(".ass").name)
		cmd = [
			'ffmpeg',
			'-y',
			'-i',
			F'{input_file}',
			'-vn',
			'-an',
			F'{output}'
		]

		common.run_process(cmd, silent=True)
		return output
	@staticmethod
	def build_font_list(folder: Path):
		return folder.listfiles(('.ttf', '.otf'))

	@staticmethod
	def ext_all_fonts_to_dir(p: Path, output_folder) -> Path:
		ats = mkvstuff.get_attachment_list(p)
		if len(ats) <= 0:
			return None
		for a in ats:
			id = a['id']
			out_name = a['name']

			cmd = ['mkvextract.exe']
			cmd.append('{vid_file}')
			cmd.append('attachments')
			cmd.append('{id}:{output_folder}\\{out_name}')

			for ind, c in enumerate(cmd):
				cmd[ind] = c.format(
					vid_file=str(p),
					out_name=out_name,
					id=id,
					output_folder=output_folder
				)
			common.run_process(cmd, silent=True)
		return output_folder

	@staticmethod
	def reEncodeFile(file: Path, outputFolder):
		cmd = [ "ffmpeg", "-y" ]
		cmd.append("-i")
		cmd.append(F"{file}")
		cmd.append('-map')
		cmd.append('0')
		cmd.append('-g')
		cmd.append('1')
		cmd.append('-pix_fmt')
		cmd.append('yuv420p')
		cmd.append('-c:v')
		cmd.append('h264_nvenc')
		cmd.append('-c:a')
		cmd.append('pcm_s16le')
		cmd.append('-b:v')
		cmd.append('2M')
		cmd.append('-s')
		cmd.append('1280x720')
		_output_file = outputFolder.joinpath(F"{file.stem}_re_encoded{file.suffix}")
		cmd.append(_output_file)
		common.run_process(cmd, silent=True)
		return _output_file

	@staticmethod
	def segmentListToChapterFile(segmentList: dict):
		
		randUid = lambda: "".join(str(random.randint(5, 9)) for x in range(0, 20))

		chapter = '<?xml version="1.0"?>'
		chapter += '<!-- <!DOCTYPE Chapters SYSTEM "matroskachapters.dtd"> -->\n'
		chapter += '<Chapters>\n'
		chapter += '\t<EditionEntry>\n'
		chapter += '\t\t<EditionFlagOrdered>0</EditionFlagOrdered>\n'
		chapter += '\t\t<EditionFlagHidden>0</EditionFlagHidden>\n'
		chapter += '\t\t<EditionFlagDefault>0</EditionFlagDefault>\n'
		# chapter += F'\t\t<EditionUID>{randUid()}</EditionUID>\n' # 11306657881831961012

		current_time = datetime.timedelta()

		for i in sorted(segmentList.keys()):
			seg = segmentList[i]

			startTime = F'\t\t\t<ChapterTimeStart>{seg["time_start"]}</ChapterTimeStart>\n'

			endTime = ""
			if "time_end" in seg:
				startTime = F'\t\t\t<ChapterTimeStart>{common.tdToMkvTime(current_time)}</ChapterTimeStart>\n'
				current_time += (common.parseAssTime(seg["time_end"]) - common.parseAssTime(seg["time_start"]))
				endTime = F'\t\t\t<ChapterTimeEnd>{common.tdToMkvTime(current_time)}</ChapterTimeEnd>\n'

			# if seg["segment_uid"]:
			# 	startTime = seg["previous_end"]
			# 	if i+1 in segmentList:
			# 		endTime = F'\t\t\t<ChapterTimeEnd>{segmentList[i + 1]["time_start"]}</ChapterTimeEnd>\n'

			chapter += '\t\t<ChapterAtom>\n'
			# chapter += F'\t\t\t<ChapterUID>{randUid()}</ChapterUID>\n'
			chapter += '\t\t\t<ChapterFlagHidden>0</ChapterFlagHidden>\n'
			chapter += '\t\t\t<ChapterFlagEnabled>1</ChapterFlagEnabled>\n'
			chapter += startTime
			chapter += endTime
			chapter += '\t\t\t<ChapterDisplay>\n'
			chapter += F'\t\t\t\t<ChapterString>{seg["name"]}</ChapterString>\n' if seg["name"] not in ("?", "", None) else ""
			chapter += '\t\t\t\t<ChapterLanguage>eng</ChapterLanguage>\n'
			chapter += '\t\t\t</ChapterDisplay>\n'
			chapter += '\t\t</ChapterAtom>\n'

		chapter += '\t</EditionEntry>\n'
		chapter += '</Chapters>'

		return chapter
		

	@staticmethod
	def has_chapters(input_file: Path) -> bool:
		js = mkvstuff.mkvJson(input_file)
		if 'chapters' not in js:
			return False
		if len(js['chapters']) > 0:
			return True
		return False

	@staticmethod
	def extract_chapter_if_available(input_file: Path, output_folder: Path) -> Union[None, Path]:
		if not mkvstuff.has_chapters(input_file):
			return None
		return mkvstuff.extract_chapter(input_file, output_folder=output_folder)

	@staticmethod
	def segmentFreeChapter(input_file: Path, output_folder: Path):
		if chapter := mkvstuff.extract_chapter_if_available(input_file, output_folder):
			new_chap = chapter.append_stem("no_segments")
			with chapter.open("r", encoding="utf-8") as f, new_chap.open("w", encoding="utf-8") as nf:
				for line in f:
					if '<ChapterSegmentUID' not in line:
						nf.write(line)
			chapter.unlink()
			return new_chap
		return None

	@staticmethod
	def extract_chapter(input_file: Path, output_folder: Path = Path(".")) -> Path:
		cmd = ['mkvextract.exe']
		cmd.append(str(input_file))
		cmd.append('chapters')
		full_output_path = output_folder.joinpath(input_file.with_suffix(".xml").name)
		cmd.append(str(full_output_path))
		common.run_process(cmd, silent=True)
		return full_output_path

	@staticmethod
	def splitFilesByTimeCodes(input_file: Path, split_times: list, output_file: Path, viaFfmpeg=True, reEncode=False) -> List[Path]:
		print([x for x in split_times])

		if viaFfmpeg: 
			ffmpegTimeStamps = []
			ffmpegStartTime = ""

			parts = {}

			for x in split_times:
				if not len(ffmpegTimeStamps):
					ffmpegStartTime = ""
					ffmpegTimeStamps
				ffmpegTimeStamps.append((x[0], ffmpegStartTime, x[1]))
				ffmpegStartTime = x[1]

			print(F"Splitting {input_file.name} into parts...")

			output_file.parent.mkdir(exist_ok=True, parents=True)

			for fts in ffmpegTimeStamps:
				partId = fts[0]
				cmd = [ "ffmpeg", "-y" ]				
				cmd.append("-i")
				cmd.append(F"{input_file}")
				if fts[1] != "":
					cmd.append("-ss")
					cmd.append(fts[1])
				
				cmd.append("-to")
				cmd.append(fts[2])

				if not reEncode:
					cmd.append('-c')
					cmd.append('copy')
				else:
					cmd.append('-map')
					cmd.append('0')
					cmd.append('-g')
					cmd.append('1')
					cmd.append('-pix_fmt')
					cmd.append('yuv420p')
					cmd.append('-c:v')
					cmd.append('h264_nvenc')
					cmd.append('-c:a')
					cmd.append('pcm_s16le')
					cmd.append('-b:v')
					cmd.append('2M')
					cmd.append('-s')
					cmd.append('1280x720')


				_output_file = output_file.parent.joinpath(F"{output_file.stem}_{partId}{output_file.suffix}")
				cmd.append(_output_file)
				print(F"\rSplitting{' and re-encoding' if reEncode else ''} Part ID#{partId}...", end="")
				common.run_process(cmd, silent=True)
				print(F"\rSplitting{' and re-encoding' if reEncode else ''} Part ID#{partId}, DONE!", end="\n")

				parts[fts[0]] = _output_file
			return parts
		else:
			ids = [x[0] for x in split_times]
			timeCodes = ",".join(x[1] for x in split_times)
			# print(timeCodes)
			cmd = [
				"mkvmerge",
				"--ui-language",
				"en",
				"--output",
				F"{output_file}",
				"(",
				F"{input_file}",
				")",
				"--split",
				F"timestamps:{timeCodes}",
			]

			print(F"Splitting {input_file} into parts...")

			common.run_process(cmd, silent=True)
			assumed_files = {}
			for x in range(1, len(ids) + 1):
				_af = output_file.parent.joinpath(output_file.append_stem(F"-{x:03}").name)
				if not _af.is_file():
					raise Exception(F"Assumed split part:' {_af} does not exist. Good luck.")
				assumed_files[ids[x-1]] = _af
			print(assumed_files)
			return assumed_files

	@staticmethod
	def mkvJson(input_file: Path):
		cmd = ['mkvmerge.exe']
		cmd.append('-J')
		cmd.append(str(input_file))
		rJson = common.run_process(cmd, silent=True)
		return json.loads(rJson)
