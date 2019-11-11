import argparse
import traceback
from pprint import pprint
from typing import AnyStr, List, Optional, Tuple, Union

from lib.common import common
from lib.mkvstuff import mkvstuff
from lib.pathlibex import Path

pp = lambda s: pprint(s, indent=4)

'''
MKVUnlink in Python because MKVUnlink did not work on this shitty coalgirls release. Stupid linked segments.
Very crude, may or may not work, no guarantees, good luck.
'''


class PyMergeMKVLinks():
	def __init__(self, args):
		self.sourceFolder: Path = args.sourceDir[0]
		self.sourceFolder.mkdir(exist_ok=True)
		self.outputFolder: Path = args.destDir[0]
		self.outputFolder.mkdir(exist_ok=True)
		self.sourceFiles = self.generateFileList()
		self.tmpDir = Path("_unlink_temp/")
		self.tmpDir.mkdir(exist_ok=True)
		self.processFiles()

	def generateFileList(self):
		segs = {}
		for f in self.sourceFolder.listfiles():
			js = mkvstuff.mkvJson(f)
			segs[js["container"]["properties"]["segment_uid"]] = f
		return segs

	def processFiles(self):
		for i, (segmentUid, sourceFile) in enumerate(self.sourceFiles.items()):
			sourceFile: Path
			if segments := mkvstuff.getChapterDict(sourceFile):
				if not len([x for x in segments.values() if x["segment_uid"]]):
					self.plainCopy(sourceFile, self.outputFolder.joinpath(sourceFile.name))
					continue
				if segmentList := self.buildSegmentList(sourceFile, segments, self.tmpDir.joinpath(str(i))):
					new_chapter = self.tmpDir.joinpath(str(i)).joinpath("new_chapter.xml")
					with new_chapter.open('w', encoding='utf-8') as f:
						 f.write(mkvstuff.segmentListToChapterFile(segmentList))

					# mkvstuff.segmentFreeChapter(sourceFile, self.tmpDir.joinpath(str(i)))
					self.buildMkvFromSegments(segmentList, self.outputFolder.joinpath(sourceFile.name), self.tmpDir.joinpath(str(i)), chapter=new_chapter)

	def plainCopy(self, sourceFile: Path, destinationFile: Path):
		print(F"Plain copying {sourceFile} to {destinationFile}")
		sourceFile.copy(destinationFile)

	def buildMkvFromSegments(self, segmentList, output_file: Path, tmpDir: Path, chapter=None):
		concat_file = Path("concat.txt")
		font_dir = tmpDir.joinpath("fonts")
		font_dir.mkdir(exist_ok=True)
		style_list = {}
		for i in sorted(segmentList.keys()):
			seg = segmentList[i]
			if 'file_path' not in seg:
				continue

			mkvstuff.ext_all_fonts_to_dir(seg['file_path'], font_dir)
			sub_file = mkvstuff.extract_first_subtitle(seg['file_path'], tmpDir)

			sub_file = mkvstuff.suffixStyleNaming(sub_file, F"partid_{i}")  # silly double up

			for styleStr in mkvstuff.getStylesFromAssFile(sub_file):
				styleDict = mkvstuff.style_to_dict(styleStr)
				style_list[styleDict["name"]] = styleDict

			sub_file.unlink()

		for i in sorted(segmentList.keys()):
			seg = segmentList[i]
			if 'file_path' not in seg:
				continue
			_fixed_sub = mkvstuff.extract_first_subtitle(seg["file_path"], tmpDir)
			_fixed_sub = mkvstuff.suffixStyleNaming(_fixed_sub, F"partid_{i}") # silly double up, but too lazy to save in memory 
			_fixed_sub = mkvstuff.replaceAssStylesWithList(_fixed_sub, style_list)
			_fixed_sub_mkv = mkvstuff.replaceSubFileWith(seg["file_path"], _fixed_sub, tmpDir)
			segmentList[i]["file_path"] = _fixed_sub_mkv

		with concat_file.open("w", encoding="utf-8") as f:
			for i in sorted(segmentList.keys()):
				seg = segmentList[i]
				if 'file_path' not in seg:
					continue
				f.write(F"file '{seg['file_path']}'\n")

		_fixed_sub.unlink()

		output_file_tmp = output_file.append_stem('_tmp')

		cmd = [
			'ffmpeg',
			'-y',
			'-f',
			'concat',
			'-safe',
			'0',
			'-i',
			F'{concat_file}',
			'-c',
			'copy',
			F'{output_file_tmp}',
		]

		fonts_list = mkvstuff.build_font_list(font_dir)

		print(F"Merging into: {output_file_tmp}")
		common.run_process(cmd, silent=True)
		concat_file.unlink()

		output_file = output_file.parent.joinpath(common.strip_crc(output_file.stem) + output_file.suffix)

		print(F"Merging (with chapter & fonts) into: {output_file}")
		cmd = [
			"mkvmerge",
			"--ui-language",
			"en",
			"--output",
			F"{output_file}",
			"(",
			F"{output_file_tmp}",
			")",
			"--chapter-language",
			"eng",
			"--chapters",
			F"{chapter}",
		]
		for font in fonts_list:
			cmd.extend(
				[
					"--attachment-name",
					F"{font.name}",
					"--attachment-mime-type",
					F"{font.mime}",
					"--attach-file",
					F"{font.resolve()}"
				]
			)
		common.run_process(cmd, silent=True)
		output_file_tmp.unlink()
		print("\rCalculating and appending CRC-Sum...", end='')
		csum = common.crc32f(output_file)
		output_file.move(output_file.append_stem(F' [{csum}]'))
		print(F"\rCalculating and appending CRC-Sum, OK: {csum}")

		# cmd = [
		# 	"mkvmerge",
		# 	"--ui-language",
		# 	"en",
		# 	"--output",
		# 	F"{output_file}",
		# ]

		# for i in sorted(segmentList.keys()):
		# 	seg = segmentList[i]
		# 	cmd.extend([
		# 		"(",
		# 		F"{seg['file_path']}",
		# 		")",
		# 		"+"
		# 	])
		# del cmd[-1]

		# cmd.extend([
		# 	"--track-order",
		# 	"0:0,0:1,0:2",
		# 	"--append-to",
		# 	"1:0:0:0,2:0:1:0,3:0:2:0,4:0:3:0,1:1:0:1,2:1:1:1,3:1:2:1,4:1:3:1,1:2:0:2,2:2:1:2,3:2:2:2,4:2:3:2"
		# ])

		# [
		# 	"--ui-language",
		# 	"en",
		# 	"--output",
		# 	"K:\\unlink_mkv_py\\_unlink_temp\\0\\Tokyo Ghoul 02 Incubation.mkv",
		# 	"(",
		# 	"K:\\unlink_mkv_py\\_unlink_temp\\0\\parts-001.mkv",
		# 	")",
		# 	"+",
		# 	"(",
		# 	"K:\\unlink_mkv_py\\videos\\[Coalgirls]_Tokyo_Ghoul_NCOP1_(1920x1080_Blu-ray_FLAC)_[D91E552D].mkv",
		# 	")",
		# 	"+",
		# 	"(",
		# 	"K:\\unlink_mkv_py\\_unlink_temp\\0\\parts-002.mkv",
		# 	")",
		# 	"+",
		# 	"(",
		# 	"K:\\unlink_mkv_py\\videos\\[Coalgirls]_Tokyo_Ghoul_NCED1a_(1920x1080_Blu-ray_FLAC)_[23319A8D].mkv",
		# 	")",
		# 	"+",
		# 	"(",
		# 	"K:\\unlink_mkv_py\\_unlink_temp\\0\\parts-003.mkv",
		# 	")",
		# 	"--track-order",
		# 	"0:0,0:1,0:2",
		# 	"--append-to",
		# 	"1:0:0:0,2:0:1:0,3:0:2:0,4:0:3:0,1:1:0:1,2:1:1:1,3:1:2:1,4:1:3:1,1:2:0:2,2:2:1:2,3:2:2:2,4:2:3:2"
		# ]
	#:

	def buildSegmentList(self, input_file: Path, segmentList: dict, outputDirectory: Path = None, fullOutputDirectory: Path = None):
		if not outputDirectory and not fullOutputDirectory:
			raise Exception("mergeSegmentsIntoFile requires either outputDirectory or fullOutputDirectory to be set")

		# split_times = []
		# for i, seg in segmentList.items():
			# if seg["segment_uid"] is None and (segmentList[i + 1]["segment_uid"] if (i + 1) < len(segmentList) else True):

		split_times = []
		for i in sorted(segmentList.keys()):
			seg = segmentList[i]
			if seg["segment_uid"] is None and (segmentList[i + 1]["segment_uid"] if (i + 1) < len(segmentList) else True):
				if "time_end" not in seg:
					if i + 1 in segmentList:
						split_times.append((i, segmentList[i+1]["time_start"]))
					elif i - 1 in segmentList and 'time_end' in segmentList[i-1]:
						split_times.append((i, segmentList[i-1]["time_end"]))
				else:
					#split_times.append(seg["time_start"])
					split_times.append((i, seg["time_end"]))
			else:
				if seg["segment_uid"] in self.sourceFiles:
					segmentList[i]["file_path"] = self.sourceFiles[seg["segment_uid"]]

		# split_times = [(i, seg["time_end"]) for (i, seg) in segmentList.items() if seg["segment_uid"] is None and (segmentList[i + 1]["segment_uid"] if (i + 1) < len(segmentList) else True)]

		output_file: Path = None 
		if fullOutputDirectory:
			output_file = fullOutputDirectory
		else:
			output_file = outputDirectory.joinpath(input_file.change_stem("parts").name)

		split_files = mkvstuff.splitFilesByTimeCodes(input_file, split_times, output_file)

		print(F"Files are: {','.join(str(x) for x in split_files)}")

		for i, seg in segmentList.items():
			if i in split_files:
				segmentList[i]["file_path"] = split_files[i]

		# pp(segmentList)
		return segmentList
	#:

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="")

	parser.set_defaults(which="main_p")
	# parser.add_argument("-e", "--specific-episodes", action="store", dest="workOnSpecificEpisodes", default=None)
	# parser.add_argument("-nc", "--no-checksums", action="store_true", dest="noCheckSums", default=None)
	# parser.add_argument("-wc", "--with-checksums", action="store_true", dest="withCheckSums", default=None)

	parser.add_argument("sourceDir", nargs="+", type=common.folderArgument)
	parser.add_argument("destDir", nargs="*", type=common.folderArgument, default=(Path("./_output/"), ))
	# parser.add_argument("sourceDir", type=common.folderArgument, nargs="?", required=False)
	# parser.add_argument("destDir", type=common.folderArgument, nargs="?", default=Path("_MERGED"), required=False)


	args = parser.parse_args()
	try:
		PyMergeMKVLinks(args)
	except KeyboardInterrupt:
		traceback.print_exc()
		print("I hate KeyboardInterrupt")
		exit(1)
