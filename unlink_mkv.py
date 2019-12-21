import argparse
import traceback
from pprint import pprint
from typing import AnyStr, List, Optional, Tuple, Union

from lib.common import common
from lib.mkvstuff import mkvstuff
from lib.pathlibex import Path

'''
MKVUnlink in Python because MKVUnlink did not work on this shitty coalgirls release. Stupid linked segments.
Very crude, may or may not work, no guarantees, good luck.
'''


class PyMergeMKVLinks():
	def __init__(self, args):
		self.sourceFolder: Path = args.sourceDir[0]
		self.outputFolder: Path = args.destDir[0]
		self.outputFolder.mkdir(exist_ok=True)
		self.sourceFiles = self.generateFileList()
		if not len(self.sourceFiles):
			print(F"Found no files with segments in: {self.sourceFolder}")
			exit(1)
		self.tmpDir = Path("_unlink_temp/")
		self.tmpDir.mkdir(exist_ok=True)
		self.processFiles()

	def generateFileList(self):
		segs = {}
		for f in self.sourceFolder.listfiles():
			js = mkvstuff.mkvJson(f)
			if "properties" in js["container"]:
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
			_fixed_sub = mkvstuff.suffixStyleNaming(_fixed_sub, F"partid_{i}")  # silly double up, but too lazy to save in memory
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

	def buildSegmentList(self, input_file: Path, segmentList: dict, outputDirectory: Path = None, fullOutputDirectory: Path = None):
		if not outputDirectory and not fullOutputDirectory:
			raise Exception("mergeSegmentsIntoFile requires either outputDirectory or fullOutputDirectory to be set")

		split_times = []
		for i in sorted(segmentList.keys()):
			seg = segmentList[i]
			if seg["segment_uid"] is None and (segmentList[i + 1]["segment_uid"] if (i + 1) < len(segmentList) else True):
				if "time_end" not in seg:
					if i + 1 in segmentList:
						split_times.append((i, segmentList[i + 1]["time_start"]))
					elif i - 1 in segmentList and 'time_end' in segmentList[i - 1]:
						split_times.append((i, segmentList[i - 1]["time_end"]))
				else:
					split_times.append((i, seg["time_end"]))
			else:
				if seg["segment_uid"] in self.sourceFiles:
					segmentList[i]["file_path"] = self.sourceFiles[seg["segment_uid"]]

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

		return segmentList


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="")

	parser.set_defaults(which="main_p")
	parser.add_argument("sourceDir", nargs="+", type=common.folderArgument)
	parser.add_argument("destDir", nargs="*", type=common.folderArgument, default=(Path("./_output/"), ))
	args = parser.parse_args()
	try:
		PyMergeMKVLinks(args)
	except KeyboardInterrupt:
		traceback.print_exc()
		print("I hate KeyboardInterrupt")
		exit(1)
